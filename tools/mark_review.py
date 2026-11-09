"""Mark a new RGB PNG delivery copy and verify its experimental provenance tag.

This is identification, not copy prevention, signed C2PA or ownership proof.
Keep the existing 32-byte key private. Owner/work labels are only HMAC inputs;
they are never written to PNG metadata or reports. Visible provider attribution,
rights records and actual visual review remain separate required steps. Altered
pixels also require rebuilding any downstream manifests and reviewing the result.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import io
import json
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from src.provenance_watermark import VERSION, detect, embed, load_key


def _png(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.format != 'PNG' or image.mode != 'RGB':
            raise ValueError('Require an RGB PNG delivery copy')
        image.load()
        return image.copy()


def _limits():
    return dict(copy_prevention=False, c2pa_signed=False, ownership_certification=False,
                visual_review='not_performed', provider_attribution='required_separately')


def init_key(key_file):
    """Create a private random 32-byte key once; never replace an existing file."""
    path = Path(key_file)
    if path.exists() or path.is_symlink():
        raise FileExistsError('Preserve every existing key')
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    with path.open('xb') as stream:
        stream.write(key)
    if not hmac.compare_digest(load_key(path), key):
        raise OSError('Key readback failed')
    return dict(status='key_created')


def mark_image(source, output, *, owner, work_id, key_file, protected_top=0):
    """Issue a fresh file only after encoded PNG pixels pass keyed detection."""
    if any(not isinstance(value, str) or not value.strip() or len(value) > 256
           for value in (owner, work_id)):
        raise ValueError('Require nonempty owner and work ID, each at most 256 characters')
    source, output = Path(source), Path(output)
    if output.suffix.lower() != '.png':
        raise ValueError('Output must have a PNG extension')
    if output.exists() or output.is_symlink() or source.resolve() == output.resolve():
        raise FileExistsError('Preserve all existing files')
    key = load_key(key_file)
    source_bytes = source.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    identity = json.dumps([owner, work_id, source_sha], ensure_ascii=False,
                          separators=(',', ':')).encode('utf-8')
    asset_id = hmac.digest(key, b'toon-review-tag-v1:' + identity, 'sha256')[:8]
    image = _png(source_bytes)
    marked, record = embed(image, key, asset_id, protected_top=protected_top)
    stream = io.BytesIO()
    marked.save(stream, format='PNG')
    encoded = stream.getvalue()
    observed = detect(_png(encoded), key)
    if not observed['detected'] or observed['asset_id'] != asset_id.hex():
        raise ValueError('Encoded PNG failed watermark verification')
    created = False
    try:
        with output.open('xb') as destination:
            created = True
            destination.write(encoded)
        written = output.read_bytes()
        if written != encoded:
            raise OSError('Output readback differs from verified PNG')
    except OSError:
        if created:
            output.unlink(missing_ok=True)
        raise
    return dict(status='marked_and_verified', version=VERSION,
                source_sha256=source_sha, output_sha256=hashlib.sha256(written).hexdigest(),
                output_bytes=len(written), width=image.width, height=image.height,
                protected_top=protected_top, source_metadata_copied=False,
                watermark=record, detection=observed, **_limits())


def verify_image(source, *, key_file, expected_sha256=None, expected_asset_id=None):
    """Check pixels and optional report hashes without modifying the input."""
    for value, size in ((expected_sha256, 64), (expected_asset_id, 16)):
        if value is not None and not re.fullmatch('[a-fA-F0-9]{' + str(size) + '}', value):
            raise ValueError('Expected hashes and asset IDs must be hexadecimal')
    key = load_key(key_file)
    data = Path(source).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    result = detect(_png(data), key)
    hash_matches = None if expected_sha256 is None else hmac.compare_digest(digest, expected_sha256.lower())
    asset_matches = None if expected_asset_id is None else result['asset_id'] == expected_asset_id.lower()
    verified = result['detected'] and hash_matches is not False and asset_matches is not False
    return dict(status='verified' if verified else 'not_verified', version=VERSION,
                image_sha256=digest, image_bytes=len(data), detection=result,
                expected_sha256_matches=hash_matches, expected_asset_id_matches=asset_matches,
                **_limits())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    initializer = commands.add_parser('init-key', help='Create a new private 32-byte key; never overwrite')
    initializer.add_argument('key_file', type=Path)
    marker = commands.add_parser('embed', help='Create a new marked RGB PNG; never overwrite')
    marker.add_argument('source', type=Path)
    marker.add_argument('output', type=Path)
    marker.add_argument('--owner', required=True, help='Private label, excluded from output')
    marker.add_argument('--work-id', required=True, help='Private label, excluded from output')
    marker.add_argument('--key-file', type=Path, required=True, help='Existing private 32-byte key')
    marker.add_argument('--protected-top', type=int, default=0, help='Preserve visible notice pixels above this row')
    verifier = commands.add_parser('verify', help='Read-only keyed pixel and optional file-hash check')
    verifier.add_argument('source', type=Path)
    verifier.add_argument('--key-file', type=Path, required=True)
    verifier.add_argument('--sha256', dest='expected_sha256')
    verifier.add_argument('--asset-id', dest='expected_asset_id')
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        if command == 'init-key':
            result = init_key(**args)
        else:
            result = mark_image(**args) if command == 'embed' else verify_image(**args)
    except (OSError, ValueError) as error:
        # Exception text can contain local paths or key filenames.
        code = ('destination_exists' if isinstance(error, FileExistsError) else
                'required_file_missing' if isinstance(error, FileNotFoundError) else
                'invalid_input' if isinstance(error, ValueError) else 'file_operation_failed')
        print(json.dumps(dict(status='error', error=code)))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] in {'key_created', 'marked_and_verified', 'verified'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
