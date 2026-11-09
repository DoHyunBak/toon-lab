"""Validate or export an explicit source-only release. No network or Git writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import unicodedata
import zipfile


MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_FILES = 512
POLICY = "public-release.json"
MANIFEST = "RELEASE_MANIFEST.json"
REQUIRED = {"README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"}
RESERVED = {POLICY.casefold(), MANIFEST.casefold()}
PRIVATE_ROOTS = {".agents", ".codex", ".git", ".venv", "__pycache__", ".pytest_cache",
                 "tmp", "dist", "vendor", "skills", "node_modules", "build"}
PRIVATE_FILES = {"agents.md", "claude.md", "skills-lock.json",
                 "tools/prepare_pui_season.py", "tools/build_pui_discovery.py",
                 "tests/test_legal_closure_facts.py", "tests/test_research_expression_storage.py",
                 "tests/test_discovery_handoff.py"}
PUBLIC_FIXTURES = {"workspace/01_scripts/example.json", "workspace/workflow_api.example.json"}
SHOWCASE_PNG = "docs/public/examples/webtoon-preview.png"
SHOWCASE_SHA256 = "87914023d3b63fd0ac55101ddb3501c9cc559de2de1a1c462ee4600a054d58ae"
TEXT_SUFFIXES = {".py", ".ps1", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg"}
TEXT_NAMES = {"LICENSE", "NOTICE", ".gitignore", ".gitattributes", ".env.example"}
PUBLIC_ROOTS = {"src", "tests", "tools", "docs", ".github"}
PUBLIC_ROOT_FILES = {"readme.md", "license", "notice", "third_party_notices.md", "security.md",
                     "contributing.md", "open_source_release.md", "requirements.txt", "factory.ps1", "compress_png.py",
                     "pyproject.toml", "pytest.ini", ".gitignore", ".gitattributes", ".env.example", "agents.md"}
PUBLIC_AGENT_GUIDE_SOURCE = "docs/public/REPO_AGENT_GUIDE.md"
PROVIDER_KEY = re.compile(r"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")
PERSONAL_PATH = re.compile(r"(?i)(?:[A-Z]:[\\/]+Users[\\/]+[^\s\\/\"']+|/(?:Users|home)/[^\s/\"']+)")
STORY_WORKSPACE_PATH = re.compile(r'''(?i)\bworkspace[\\/]+works[\\/]+[^\s\\/"'<>]+''')
CREDENTIAL_NAME = re.compile(r"(?i)(?:api[_-]?key|api[_-]?token|access[_-]?token|auth[_-]?token|client[_-]?secret|private[_-]?key|password|secret[_-]?access[_-]?key|(?:github|typesafe|openai)[_-]?token)$")
CREDENTIAL_ASSIGNMENT = re.compile(r"(?i)(?:[\"']?([A-Z][A-Z0-9_-]*(?:API[_-]?KEY|ACCESS[_-]?TOKEN|AUTH[_-]?TOKEN|CLIENT[_-]?SECRET|PASSWORD|PRIVATE[_-]?KEY)|api_key|access_token|password|client_secret)[\"']?)\s*[:=]\s*[\"']([^\"'\r\n]+)[\"']")
UNQUOTED_CREDENTIAL = re.compile(r"(?im)^\s*[A-Z0-9_-]*(?:API_KEY|API_TOKEN|ACCESS_TOKEN|AUTH_TOKEN|CLIENT_SECRET|PASSWORD|PRIVATE_KEY)\s*[:=]\s*([A-Za-z0-9_./+=:@~-]{8,})\s*(?:#.*)?$")
URL_USERINFO = re.compile(r"https?://[^/\s:@]+:[^/\s@]+@", re.IGNORECASE)
AUTHORIZATION_LITERAL = re.compile(r"(?i)[\"']authorization[\"']\s*:\s*[\"'](?:Bearer|Basic)\s+([A-Za-z0-9_+/=.-]{8,})[\"']")
PLACEHOLDER = re.compile(r"^(?:(?:YOUR|EXAMPLE|PLACEHOLDER|DUMMY)_[A-Z0-9_]+|<[^<>\r\n]+>)$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _fail(rule, path=None):
    if path and (PROVIDER_KEY.search(str(path)) or PERSONAL_PATH.search(str(path))):
        path = "<redacted-path>"
    label = f": {path}" if path else ""
    raise ValueError(f"public release blocked [{rule}]{label}")


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate-json-key")
        result[key] = value
    return result


def _json(data, rule):
    try:
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError, RecursionError):
        _fail(rule)
    if not isinstance(value, dict):
        _fail(rule)
    return value


def _name(value, *, reserved=False, public_agent_guide=False):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or value.startswith("/") or unicodedata.normalize("NFC", value) != value
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        _fail("nonportable-path")
    parts = value.split("/")
    if any(p in ("", ".", "..") or p.endswith((".", " ")) for p in parts):
        _fail("nonportable-path")
    devices = {"con", "prn", "aux", "nul", *[f"com{i}" for i in range(1, 10)],
               *[f"lpt{i}" for i in range(1, 10)]}
    if any(any(c in '<>"|?*' for c in part) or part.split(".", 1)[0].casefold() in devices
           for part in parts):
        _fail("nonportable-path")
    if PurePosixPath(value).is_absolute():
        _fail("absolute-path")
    lower = value.casefold()
    if not reserved and lower in RESERVED:
        _fail("reserved-name")
    allowed_agent_guide = public_agent_guide and value == "AGENTS.md"
    if parts[0].casefold() in PRIVATE_ROOTS or (lower in PRIVATE_FILES and not allowed_agent_guide):
        _fail("private-path", value)
    if any(p.casefold() in {".git", "__pycache__", ".pytest_cache"} for p in parts):
        _fail("private-path", value)
    if any(p.casefold().startswith(".env") for p in parts) and value != ".env.example":
        _fail("credential-file")
    if parts[0].casefold() == "workspace" and value not in PUBLIC_FIXTURES:
        _fail("private-workspace", value)
    if (len(parts) == 1 and lower not in PUBLIC_ROOT_FILES and lower not in RESERVED
            or len(parts) > 1 and parts[0].casefold() not in PUBLIC_ROOTS and value not in PUBLIC_FIXTURES):
        _fail("unreviewed-namespace", value)
    if Path(value).suffix.lower() not in TEXT_SUFFIXES and value not in TEXT_NAMES and value != SHOWCASE_PNG:
        _fail("nontext-file", value)
    return value


def _plain_path(path):
    """Reject links/junctions before resolve(), including existing ancestors."""
    try:
        path = Path(path).absolute()
    except (TypeError, ValueError, OSError):
        _fail("invalid-root-or-output-path")
    for candidate in (path, *path.parents):
        try:
            item = candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            _fail("path-not-readable")
        if (stat.S_ISLNK(item.st_mode)
                or getattr(item, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
            _fail("link-or-reparse-point")
    try:
        return path.resolve()
    except (ValueError, OSError, RuntimeError):
        _fail("path-not-resolvable")


def _root(root):
    root = _plain_path(root)
    if not root.is_dir():
        _fail("missing-root")
    return root


def _read(root, relative):
    path = _plain_path(root / relative)
    if not path.is_relative_to(root):
        _fail("outside-root")
    try:
        before = path.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
            _fail("file-type-or-size", relative)
        data = path.read_bytes()
        after = path.stat()
    except OSError:
        _fail("file-not-readable", relative)
    if ((before.st_size, before.st_mtime_ns, before.st_ino)
            != (after.st_size, after.st_mtime_ns, after.st_ino) or len(data) != before.st_size):
        _fail("file-changed-during-read", relative)
    return data


def _placeholder(value):
    return not value or bool(PLACEHOLDER.fullmatch(value))


def _known_secrets(root):
    # These values are compared in memory only, never returned or logged.
    values = {v.strip() for k, v in os.environ.items() if CREDENTIAL_NAME.search(k) and v.strip()}
    local = root / ".env"
    if local.is_file():
        _plain_path(local)
        try:
            if local.stat().st_size > 65536:
                _fail("credential-file-too-large")
            text = local.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            _fail("credential-file-not-readable")
        for line in text.splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and CREDENTIAL_NAME.search(name.strip()):
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                else:
                    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
                if value:
                    values.add(value)
    return {v for v in values if len(v) >= 8 and not _placeholder(v)}


def _scan(data, relative, secrets):
    if len(data) > MAX_FILE_BYTES:
        _fail("file-too-large", relative)
    if relative == SHOWCASE_PNG:
        if hashlib.sha256(data).hexdigest() != SHOWCASE_SHA256:
            _fail("unreviewed-showcase-image", relative)
        return
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        _fail("non-utf8-file", relative)
    if "\0" in text:
        _fail("binary-content", relative)
    label = "<redacted-path>" if PROVIDER_KEY.search(relative) or any(s in relative for s in secrets) else relative
    if any(value in text for value in secrets):
        _fail("known-credential", label)
    if PROVIDER_KEY.search(text) or PRIVATE_KEY.search(text):
        _fail("credential-marker", label)
    if URL_USERINFO.search(text):
        _fail("credential-url", label)
    if PERSONAL_PATH.search(text):
        _fail("personal-home-path", label)
    if STORY_WORKSPACE_PATH.search(text):
        _fail("story-workspace-path-content", label)
    for match in CREDENTIAL_ASSIGNMENT.finditer(text):
        if not _placeholder(match[2]) and len(match[2]) >= 8:
            _fail("credential-literal", label)
    for pattern in (UNQUOTED_CREDENTIAL, AUTHORIZATION_LITERAL):
        if any(not _placeholder(match[1]) for match in pattern.finditer(text)):
            _fail("credential-literal", label)
    if relative == ".env.example":
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            value = value.strip().strip("\"'")
            if not separator or not name.strip() or (value and not re.fullmatch(r"YOUR_[A-Z0-9_]+", value)):
                _fail("nonplaceholder-env-example", label)


def _entries(policy):
    if type(policy.get("schema_version")) is not int or policy["schema_version"] != 1 or policy.get("profile") not in ("source_workspace", "public_source_tree"):
        _fail("invalid-policy")
    entries = policy.get("files")
    if not isinstance(entries, list) or not entries or len(entries) > MAX_FILES - 2:
        _fail("invalid-policy-files")
    result, sources, targets = [], set(), set()
    for entry in entries:
        if policy["profile"] == "source_workspace":
            if not isinstance(entry, dict) or set(entry) != {"source", "target"}:
                _fail("invalid-policy-entry")
            source = _name(entry["source"])
            target = _name(entry["target"], public_agent_guide=source == PUBLIC_AGENT_GUIDE_SOURCE)
        else:
            if not isinstance(entry, str):
                _fail("invalid-public-policy-entry")
            source = target = _name(entry, public_agent_guide=entry == "AGENTS.md")
        if source.casefold() in sources or target.casefold() in targets:
            _fail("casefold-duplicate")
        sources.add(source.casefold())
        targets.add(target.casefold())
        result.append((source, target))
    if not REQUIRED.issubset({t for _, t in result}):
        _fail("missing-public-readme-or-license-notices")
    return result


def _public_policy(targets):
    return _json_bytes({"schema_version": 1, "profile": "public_source_tree", "files": sorted(targets)})


def collect_payload(root):
    """Return reviewed UTF-8 bytes plus generated public policy; no manifest yet."""
    root = _root(root)
    secrets = _known_secrets(root)
    policy_data = _read(root, POLICY)
    _scan(policy_data, POLICY, secrets)
    policy = _json(policy_data, "invalid-policy-json")
    entries = _entries(policy)
    payload = {}
    for source, target in entries:
        data = _read(root, source)
        _scan(data, target, secrets)
        payload[target] = data
    payload[POLICY] = _public_policy(payload)
    if sum(map(len, payload.values())) > MAX_TOTAL_BYTES:
        _fail("total-size-limit")
    return payload


def _manifest(payload):
    return _json_bytes({"schema_version": 1, "files": {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        for name, data in sorted(payload.items())}})


def _fresh_output(root, path, sources):
    target = _plain_path(path)
    if target.exists() or target == root or root.is_relative_to(target):
        _fail("output-must-be-fresh")
    if target.is_relative_to(root):
        top = target.relative_to(root).parts[0].casefold()
        if top in PUBLIC_ROOTS | (PRIVATE_ROOTS - {"dist", "tmp"}):
            _fail("output-inside-source-or-internal-directory")
    for source in sources:
        parent = (root / source).parent
        if parent != root and target.is_relative_to(parent):
            _fail("output-inside-selected-source-directory")
    return target


def export_release(root, dest, zip_path=None):
    """Snapshot selected bytes, then create fresh output/optional deterministic ZIP."""
    root = _root(root)
    payload = collect_payload(root)
    policy_data = _read(root, POLICY)
    _scan(policy_data, POLICY, _known_secrets(root))
    policy = _json(policy_data, "invalid-policy-json")
    entries = _entries(policy)
    dest = _fresh_output(root, dest, [s for s, _ in entries])
    archive = _fresh_output(root, zip_path, [s for s, _ in entries]) if zip_path is not None else None
    if archive == dest:
        _fail("archive-output-collision")
    payload[MANIFEST] = _manifest(payload)
    try:
        _plain_path(dest.parent)
        dest.mkdir(parents=True, exist_ok=False)
        for relative, data in sorted(payload.items()):
            path = dest / relative
            _plain_path(path.parent)
            path.parent.mkdir(parents=True, exist_ok=True)
            _plain_path(path.parent)
            with path.open("xb") as stream:
                stream.write(data)
        if archive is not None:
            _plain_path(archive.parent)
            archive.parent.mkdir(parents=True, exist_ok=True)
            _plain_path(archive.parent)
            with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
                for name, data in sorted(payload.items()):
                    entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    entry.create_system = 3
                    entry.external_attr = (stat.S_IFREG | 0o644) << 16
                    output.writestr(entry, data)
    except (OSError, zipfile.BadZipFile):
        _fail("cannot-create-fresh-output")
    if archive is not None:
        verify_archive(archive)
    return {"status": "passed", "output_dir": str(dest), "zip": str(archive) if archive else None,
            "file_count": len(payload), "bytes": sum(map(len, payload.values())),
            "network_or_git_write": False}


def _verify_payload(payload, secrets):
    if not {POLICY, MANIFEST}.issubset(payload):
        _fail("missing-release-metadata")
    policy = _json(payload[POLICY], "invalid-public-policy-json")
    if policy.get("profile") != "public_source_tree" or set(policy) != {"schema_version", "profile", "files"}:
        _fail("invalid-public-policy")
    expected = {target for _, target in _entries(policy)} | {POLICY, MANIFEST}
    if set(payload) != expected:
        _fail("archive-policy-file-set-mismatch")
    manifest = _json(payload[MANIFEST], "invalid-release-manifest-json")
    if (set(manifest) != {"schema_version", "files"} or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 1 or not isinstance(manifest.get("files"), dict)):
        _fail("invalid-release-manifest")
    if set(manifest["files"]) != expected - {MANIFEST}:
        _fail("manifest-file-set-mismatch")
    for name, data in payload.items():
        _scan(data, name, secrets)
        if name == MANIFEST:
            continue
        record = manifest["files"][name]
        if (not isinstance(record, dict) or set(record) != {"sha256", "bytes"}
                or not isinstance(record.get("sha256"), str) or not SHA256.fullmatch(record["sha256"])
                or type(record.get("bytes")) is not int or record["bytes"] != len(data)
                or record["sha256"] != hashlib.sha256(data).hexdigest()):
            _fail("manifest-content-mismatch", name)


def _zip_envelope(raw, entries):
    """Our release format has no hidden comments, extra records or trailing data."""
    if len(raw) < 22 or raw[-22:-18] != b"PK\x05\x06":
        _fail("archive-envelope")
    try:
        _, disk, start_disk, disk_count, count, central_size, central_offset, comment = struct.unpack("<4s4H2LH", raw[-22:])
        if (disk or start_disk or comment or disk_count != count or count != len(entries)
                or central_offset + central_size != len(raw) - 22):
            _fail("archive-envelope")
        offset, expected_central = 0, 0
        for entry in entries:
            if entry.header_offset != offset:
                _fail("archive-hidden-record")
            fields = struct.unpack("<4s5H3I2H", raw[offset:offset + 30])
            signature, _, flags, method, _, _, crc, compressed, size, name_size, extra_size = fields
            name = entry.filename.encode("utf-8" if flags & 0x800 else "cp437")
            if (signature != b"PK\x03\x04" or flags & ~0x800 or flags != entry.flag_bits
                    or method != entry.compress_type or crc != entry.CRC or compressed != entry.compress_size
                    or size != entry.file_size or extra_size or name_size != len(name)
                    or raw[offset + 30:offset + 30 + name_size] != name):
                _fail("archive-local-header")
            offset += 30 + name_size + compressed
            expected_central += 46 + name_size
        if offset != central_offset or expected_central != central_size:
            _fail("archive-hidden-record")
    except (struct.error, UnicodeError):
        _fail("archive-envelope")


def verify_archive(path):
    """Check archive names, budgets, exact policy/manifest and UTF-8 in memory."""
    path = _plain_path(path)
    try:
        if not path.is_file() or path.stat().st_size > MAX_TOTAL_BYTES + MAX_FILE_BYTES:
            _fail("archive-size-or-type")
        raw = path.read_bytes()
        if len(raw) > MAX_TOTAL_BYTES + MAX_FILE_BYTES:
            _fail("archive-size-or-type")
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_FILES:
                _fail("archive-file-count")
            if archive.comment:
                _fail("archive-hidden-metadata")
            payload, names, total = {}, set(), 0
            for entry in entries:
                name = _name(entry.filename, reserved=True, public_agent_guide=True)
                if name.casefold() in names:
                    _fail("archive-duplicate-name")
                names.add(name.casefold())
                mode = entry.external_attr >> 16
                if (entry.is_dir() or stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                        or entry.external_attr & 1024 or entry.extra or entry.comment
                        or entry.flag_bits & ~0x800 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                    _fail("archive-entry-type", name)
                if entry.file_size > MAX_FILE_BYTES:
                    _fail("archive-entry-size", name)
                total += entry.file_size
                if total > MAX_TOTAL_BYTES + MAX_FILE_BYTES:
                    _fail("archive-total-size")
                data = archive.read(entry)
                if len(data) != entry.file_size:
                    _fail("archive-entry-size", name)
                payload[name] = data
            _zip_envelope(raw, entries)
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        _fail("archive-not-readable")
    secrets = _known_secrets(path.parent) | _known_secrets(Path(__file__).resolve().parents[1])
    _verify_payload(payload, secrets)
    return {"status": "passed", "file_count": len(payload), "bytes": sum(map(len, payload.values())),
            "extracted": False, "credential_scan": "patterns-and-locally-known-values; not a proof that no secret exists"}


def _git(root, *args):
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    try:
        result = subprocess.run(["git", "-C", str(root), *args], check=False, capture_output=True,
                                env=environment, timeout=30)
    except (OSError, subprocess.SubprocessError):
        _fail("git-read-failed")
    if result.returncode:
        _fail("git-read-failed")
    return result.stdout


def check_staged(root):
    """Inspect every actual index blob, never substitute the working-tree bytes."""
    root = _root(root)
    working = _json(_read(root, POLICY), "invalid-policy-json")
    if working.get("profile") == "source_workspace":
        _fail("publish-export-only-not-private-workspace")
    secrets = _known_secrets(root)
    records = {}
    for entry in _git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_name = entry.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            name = raw_name.decode("utf-8")
        except (ValueError, UnicodeError):
            _fail("invalid-git-index-record")
        if PROVIDER_KEY.search(name) or any(value in name for value in secrets):
            _fail("credential-in-index-path")
        name = _name(name, reserved=True, public_agent_guide=True)
        if mode not in ("100644", "100755") or stage != "0" or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid):
            _fail("git-index-type-or-conflict", name)
        if name.casefold() in {n.casefold() for n in records}:
            _fail("git-index-duplicate")
        records[name] = oid
    if POLICY not in records or len(records) > MAX_FILES:
        _fail("missing-or-large-git-index-policy")
    payload = {}
    for name, oid in records.items():
        try:
            size = int(_git(root, "cat-file", "-s", oid).strip())
        except ValueError:
            _fail("invalid-git-blob-size")
        if not 0 <= size <= MAX_FILE_BYTES:
            _fail("git-blob-too-large", name)
        data = _git(root, "cat-file", "blob", oid)
        if len(data) != size:
            _fail("git-blob-size-mismatch", name)
        payload[name] = data
    _scan(payload[POLICY], POLICY, secrets)
    policy = _json(payload[POLICY], "invalid-index-policy-json")
    if policy.get("profile") != "public_source_tree" or set(policy) != {"schema_version", "profile", "files"}:
        _fail("publish-export-only-not-private-workspace")
    expected = {target for _, target in _entries(policy)} | {POLICY}
    if MANIFEST in payload:
        expected.add(MANIFEST)
    if set(payload) != expected:
        _fail("unexpected-tracked-file")
    if MANIFEST in payload:
        manifest = _json(payload[MANIFEST], "invalid-index-manifest")
        if (set(manifest) != {"schema_version", "files"} or type(manifest.get("schema_version")) is not int
                or manifest["schema_version"] != 1 or not isinstance(manifest.get("files"), dict)
                or set(manifest["files"]) != expected - {MANIFEST}):
            _fail("invalid-index-manifest")
        for record in manifest["files"].values():
            if (not isinstance(record, dict) or set(record) != {"sha256", "bytes"}
                    or not isinstance(record.get("sha256"), str) or not SHA256.fullmatch(record["sha256"])
                    or type(record.get("bytes")) is not int or not 0 <= record["bytes"] <= MAX_FILE_BYTES):
                _fail("invalid-index-manifest")
    if sum(map(len, payload.values())) > MAX_TOTAL_BYTES + MAX_FILE_BYTES:
        _fail("git-index-total-size")
    for name, data in payload.items():
        _scan(data, name, secrets)
    return {"status": "passed", "index_blobs_checked": len(payload), "git_write": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Validate only the explicit public payload")
    check.add_argument("--staged", action="store_true", help="Validate actual Git index blobs; private source workspace is rejected")
    exporter = commands.add_parser("export", help="Create a fresh source-only tree without Git initialization")
    exporter.add_argument("--output-dir", type=Path, required=True)
    exporter.add_argument("--zip", type=Path)
    verifier = commands.add_parser("verify-zip", help="Validate a release ZIP without extraction")
    verifier.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        if args.command == "check":
            result = check_staged(root) if args.staged else {"status": "passed", "file_count": len(collect_payload(root)),
                    "scope": "explicit reviewed payload only; no Git/history or legal clearance"}
        elif args.command == "export":
            result = export_release(root, args.output_dir, args.zip)
        else:
            result = verify_archive(args.archive)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError):
        # Values from files and subprocess error streams must never reach logs.
        import sys
        message = str(sys.exc_info()[1]) if isinstance(sys.exc_info()[1], ValueError) else "public release blocked [filesystem-operation]"
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
