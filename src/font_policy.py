"""Approved open fonts only; fingerprint actual bytes, never trust a filename.

New typography defaults to Pretendard Medium (500), emphasis to Bold (700).
Legacy approved Pretendard TTFs remain usable explicitly. No system fallback.
Font binaries are local production assets, not part of the source-only export.
"""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / 'assets/fonts/pretendard'
DEFAULT_FONT = FONT_DIR / 'Pretendard-Medium.otf'
BOLD_FONT = FONT_DIR / 'Pretendard-Bold.otf'
LICENSE = FONT_DIR / 'OFL.txt'
LICENSE_SHA256 = 'd31ddd9f2bed32fd7e302a205cf2380ba0de6529152d239ef99cfb6f261bfc04'
APPROVED = {
    'c89bc43027dc7cde5726e96223376f8eec09302b2fc1f8147fd5b57cfc376118': ('Pretendard SemiBold', 600),
    'c35fe941b7568d52a96010561540e47f9d3948dfde66ba25bc1908233e0a40cd': ('Pretendard ExtraBold', 800),
    'd39e50e4bb52b4993b6a4eeb821a171254745bd824446af01e1f616b89fface0': ('Pretendard Medium', 500),
    '2e91915fab54df71cc9598ebf608b2bdb54c6fe3c066ac61dff0bc44fca71cc7': ('Pretendard Bold', 700),
    '6d0af5258997aec7354a6e340fc2325ba321c410ca48b3af858c8c3d6e92a324': ('Pretendard Regular', 400),
    'eedbd2877218242323bdff816684f7f5c325e54ae820d5b78eec9a5e5c7edef6': ('Pretendard ExtraBold', 800),
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_font(path=None):
    chosen = Path(path or os.environ.get('WEBTOON_FONT') or DEFAULT_FONT).resolve()
    if not chosen.is_file() or _sha(chosen) not in APPROVED:
        raise ValueError('Unapproved or missing open font: ' + str(chosen) +
                         '. Use verified Pretendard Medium/Bold; system fonts and silent fallbacks are disabled.')
    if not LICENSE.is_file() or _sha(LICENSE) != LICENSE_SHA256:
        raise ValueError('Missing or changed approved Pretendard OFL notice')
    return chosen


def entry_font(entry, default=None):
    if entry.get('font_path'):
        return resolve_font(entry['font_path'])
    return resolve_font(BOLD_FONT if entry.get('weight') == 'bold' else default)


def font_record(path):
    path = resolve_font(path)
    return font_record_by_digest(_sha(path))


def episode_fonts(episode, default=None):
    records = {}
    for cut in episode['cuts']:
        if not isinstance(cut, dict) or not isinstance(cut.get('dialogue', []), list):
            raise ValueError('Cuts must be objects with a dialogue list')
        for entry in cut.get('dialogue', []):
            if not isinstance(entry, dict):
                raise ValueError('Dialogue entries must be objects')
            record = font_record(entry_font(entry, default))
            records[record['sha256']] = record
    return list(records.values())


def write_font_notices(directory, records):
    """Write notices, never font binaries; verify records before publication."""
    unique = {}
    for record in records:
        digest = record.get('sha256')
        if digest not in APPROVED or record != font_record_by_digest(digest):
            raise ValueError('Unverified or altered font provenance')
        unique[digest] = record
    if not LICENSE.is_file() or _sha(LICENSE) != LICENSE_SHA256:
        raise ValueError('Missing or changed approved Pretendard OFL notice')
    root = Path(directory)
    if unique:
        (root / 'licenses').mkdir(exist_ok=True)
        (root / 'licenses/Pretendard-OFL.txt').write_bytes(LICENSE.read_bytes())
    (root / 'font_licenses.json').write_text(
        json.dumps({'policy': 'open-fonts-v1', 'fonts': list(unique.values())},
                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return list(unique.values())


def font_record_by_digest(digest):
    family, weight = APPROVED[digest]
    return {'family': family, 'weight': weight, 'sha256': digest,
            'license': 'OFL-1.1', 'license_path': 'licenses/Pretendard-OFL.txt',
            'license_sha256': LICENSE_SHA256,
            'source': 'https://github.com/orioncactus/pretendard/tree/v1.3.9'}


def source_font_records(directory, manifest):
    """Validate new source provenance and notice bytes before repackaging."""
    if manifest.get('font_policy') != 'open-fonts-v1':
        return []  # Preserve existing pixels; never certify legacy fonts.
    root = Path(directory)
    records = manifest['fonts_used']
    metadata = root / 'font_licenses.json'
    if _sha(metadata) != manifest['font_licenses_sha256']:
        raise ValueError('Source font provenance changed')
    if json.loads(metadata.read_text(encoding='utf-8')) != {'policy': 'open-fonts-v1', 'fonts': records}:
        raise ValueError('Source font provenance differs from manifest')
    for record in records:
        digest = record.get('sha256')
        if digest not in APPROVED or record != font_record_by_digest(digest):
            raise ValueError('Source contains an unverified font record')
        if _sha(root / 'licenses/Pretendard-OFL.txt') != LICENSE_SHA256:
            raise ValueError('Source font license missing or changed')
    return records
