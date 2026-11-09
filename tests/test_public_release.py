"""Source-only export security contracts, using isolated synthetic files only."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools import public_release as release


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode("utf-8"))


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="public-release-test-", dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir()
        self.destination = self.base / "release"
        environment = patch.dict(os.environ, {name: "" for name in os.environ if release.CREDENTIAL_NAME.search(name)})
        environment.start()
        self.addCleanup(environment.stop)
        original_secrets = release._known_secrets
        def fixture_secrets(root):
            location = Path(root).resolve()
            return original_secrets(location) if location.is_relative_to(self.base.resolve()) else set()
        secrets = patch.object(release, "_known_secrets", side_effect=fixture_secrets)
        secrets.start()
        self.addCleanup(secrets.stop)
        self.files = [
            {"source": "README.md", "target": "README.md"},
            {"source": "LICENSE", "target": "LICENSE"},
            {"source": "THIRD_PARTY_NOTICES.md", "target": "THIRD_PARTY_NOTICES.md"},
            {"source": "src/example.py", "target": "src/example.py"},
        ]
        self.policy()
        for name, text in {
            "README.md": "# Source-only fixture\nLocal test inputs, no production data.\n",
            "LICENSE": "Synthetic license fixture, not a license grant.\n",
            "THIRD_PARTY_NOTICES.md": "Synthetic notice fixture.\n",
            "src/example.py": "VALUE = 1\n",
        }.items():
            write(self.root / name, text)

    def policy(self, entries=None):
        value = {"schema_version": 1, "profile": "source_workspace", "files": entries or self.files}
        write(self.root / "public-release.json", json.dumps(value))

    def test_windows_device_and_reserved_character_targets_are_rejected(self):
        for target in ("src/CON.py", "docs/NUL.txt", "tools/COM1.py", "src/name?.py"):
            with self.subTest(target=target):
                entries = [dict(item) for item in self.files]
                entries[-1]["target"] = target
                self.policy(entries)
                with self.assertRaises(ValueError):
                    release.collect_payload(self.root)

    def reject(self, function, forbidden=None):
        try:
            function()
        except ValueError as error:
            if forbidden:
                self.assertTrue(forbidden not in str(error), "Error echoed a synthetic credential")
            return
        self.fail("Unsafe release input was accepted")

    def export(self):
        result = release.export_release(self.root, self.destination)
        self.assertIsInstance(result, dict)
        return result

    def archive(self):
        path = self.base / "release.zip"
        release.export_release(self.root, self.destination, zip_path=path)
        self.assertTrue(path.is_file())
        return path

    def rebuild_zip(self, original, *, transform=None, extras=(), modes=None):
        target = self.base / "modified.zip"
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(target, "w") as output:
            for old in source.infolist():
                data = source.read(old.filename)
                if transform:
                    data = transform(old.filename, data)
                info = zipfile.ZipInfo(old.filename)
                info.create_system = 3
                info.external_attr = ((modes or {}).get(old.filename, stat.S_IFREG | 0o644)) << 16
                output.writestr(info, data)
            for name, data in extras:
                output.writestr(name, data)
        return target

    def test_collect_exports_only_declared_files_and_generated_public_policy(self):
        private = "/".join(("workspace", "works", "private.txt"))
        write(self.root / private, "Undeclared synthetic work must stay local.")
        payload = release.collect_payload(self.root)
        self.assertEqual(set(payload), {x["target"] for x in self.files} | {"public-release.json"})
        self.assertTrue(all(isinstance(value, bytes) for value in payload.values()))
        public_policy = json.loads(payload["public-release.json"])
        self.assertEqual(public_policy["profile"], "public_source_tree")
        self.assertNotIn(private, payload)

    def test_export_preserves_source_and_binds_exact_payload_hashes(self):
        before = {x["source"]: (self.root / x["source"]).read_bytes() for x in self.files}
        self.export()
        manifest = json.loads((self.destination / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
        expected = {x["target"] for x in self.files} | {"public-release.json"}
        self.assertEqual(set(manifest["files"]), expected)
        self.assertNotIn("RELEASE_MANIFEST.json", manifest["files"])
        for name, metadata in manifest["files"].items():
            data = (self.destination / name).read_bytes()
            self.assertEqual(metadata["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(metadata["bytes"], len(data))
        self.assertEqual(before, {x["source"]: (self.root / x["source"]).read_bytes() for x in self.files})
        self.assertIsInstance(release.collect_payload(self.destination), dict)

    def test_missing_mandatory_notice_or_source_is_rejected(self):
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "src/example.py"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.unlink()
                self.reject(lambda: release.collect_payload(self.root))
                write(path, original)

    def test_unknown_or_private_sources_and_targets_are_rejected(self):
        private_paths = [
            "." + "env",
            "/".join(("workspace", "works", "private.txt")),
            "/".join(("workspace", "references", "private.txt")),
            "/".join((".agents", "private.txt")),
            "/".join((".codex", "private.txt")),
            "tmp/private.txt",
            "vendor/private.txt",
            "unexpected/private.txt",
            "tools/prepare_" + "pui_" + "season.py",
            "tools/build_" + "pui_" + "discovery.py",
        ]
        for name in private_paths:
            for side in ("source", "target"):
                with self.subTest(name=name, side=side):
                    source = name if side == "source" else "src/extra.py"
                    target = name if side == "target" else "src/extra.py"
                    write(self.root / source, "synthetic private fixture\n")
                    self.policy(self.files + [{"source": source, "target": target}])
                    self.reject(lambda: release.collect_payload(self.root))
        self.policy()

    def test_unsafe_nonportable_paths_and_case_collisions_are_rejected(self):
        unsafe = ["../outside.py", "/outside.py", "C:" + "/outside.py", "src\\example.py", "src/../example.py"]
        for path in unsafe:
            for side in ("source", "target"):
                with self.subTest(path=path, side=side):
                    extra = {"source": "src/example.py", "target": "src/extra.py"}
                    extra[side] = path
                    self.policy(self.files + [extra])
                    self.reject(lambda: release.collect_payload(self.root))
        self.policy(self.files + [{"source": "src/example.py", "target": "SRC/EXAMPLE.PY"}])
        self.reject(lambda: release.collect_payload(self.root))

    def test_generated_policy_and_manifest_names_cannot_be_supplied(self):
        for target in ("public-release.json", "RELEASE_MANIFEST.json"):
            with self.subTest(target=target):
                self.policy(self.files + [{"source": "src/example.py", "target": target}])
                self.reject(lambda: release.collect_payload(self.root))

    def test_active_credentials_pem_and_private_home_paths_are_rejected_without_echo(self):
        credential = "s" + "k-proj-" + "A9b2C3d4E5f6" * 5
        samples = [
            credential,
            "-----BEGIN " + "PRIVATE KEY-----\nfixture\n-----END " + "PRIVATE KEY-----\n",
            "C:" + "/Users/" + "example-person/private/project.txt",
            "/home/" + "example-person/private/project.txt",
        ]
        for text in samples:
            with self.subTest(kind="synthetic forbidden content"):
                write(self.root / "src/example.py", text)
                self.reject(lambda: release.collect_payload(self.root), forbidden=credential)

    def test_actual_local_credential_value_never_enters_payload_or_error(self):
        canary = "synthetic" + "-credential-" + "do-not-export"
        write(self.root / ("." + "env"), "TYPESAFE_API_KEY" + "=" + canary + "\n")
        write(self.root / "README.md", "Accidental inclusion: " + canary)
        self.reject(lambda: release.collect_payload(self.root), forbidden=canary)
        write(self.root / "README.md", "# Safe fixture\n")
        payload = release.collect_payload(self.root)
        self.assertTrue(all(canary.encode() not in body for body in payload.values()))

    def test_story_workspace_path_literals_block_even_inside_allowed_source(self):
        parts = ("workspace", "works", "example_story", "raw", "image.png")
        for separator in ("/", "\\"):
            with self.subTest(separator=separator):
                write(self.root / "src/example.py", "IMAGE = " + repr(separator.join(parts)) + "\n")
                with self.assertRaisesRegex(ValueError, "story-workspace-path-content"):
                    release.collect_payload(self.root)
        write(self.root / "src/example.py", "DEFAULT = 'workspace/production/notice.json'\n")
        self.assertIn("src/example.py", release.collect_payload(self.root))

    def test_env_example_accepts_only_placeholder_credentials(self):
        name = "." + "env.example"
        self.policy(self.files + [{"source": name, "target": name}])
        write(self.root / name, "TYPESAFE_API_KEY=YOUR_TYPESAFE_API_KEY\n")
        self.assertIn(name, release.collect_payload(self.root))
        canary = "synthetic" + "-active-key-" + "not-a-placeholder"
        write(self.root / name, "TYPESAFE_API_KEY" + "=" + canary + "\n")
        self.reject(lambda: release.collect_payload(self.root), forbidden=canary)

    def test_symlink_source_file_and_ancestor_are_rejected(self):
        outside = self.base / "outside.py"
        write(outside, "VALUE = 2\n")
        link = self.root / "src/linked.py"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("File symlink creation is unavailable on this host")
        self.policy(self.files + [{"source": "src/linked.py", "target": "src/linked.py"}])
        self.reject(lambda: release.collect_payload(self.root))
        link.unlink()
        folder = self.base / "outside-folder"
        folder.mkdir()
        write(folder / "example.py", "VALUE = 3\n")
        link.symlink_to(folder, target_is_directory=True)
        self.policy(self.files + [{"source": "src/linked.py/example.py", "target": "src/linked.py"}])
        self.reject(lambda: release.collect_payload(self.root))

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_windows_junction_ancestor_is_rejected(self):
        outside = self.base / "junction-outside"
        outside.mkdir()
        write(outside / "example.py", "VALUE = 3\n")
        link = self.root / "src/junction"
        made = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        if made.returncode:
            self.skipTest("Junction creation is unavailable on this host")
        self.addCleanup(lambda: os.rmdir(link) if link.exists() else None)
        self.policy(self.files + [{"source": "src/junction/example.py", "target": "src/junction/example.py"}])
        self.reject(lambda: release.collect_payload(self.root))

    def test_link_and_reparse_ancestor_attributes_are_rejected_on_every_host(self):
        original = Path.lstat
        ancestor = self.root / "src"
        for mode, attributes in ((stat.S_IFLNK | 0o777, 0), (stat.S_IFDIR | 0o755, 1024)):
            def changed(path, *args, **kwargs):
                if path == ancestor:
                    return SimpleNamespace(st_mode=mode, st_file_attributes=attributes)
                return original(path, *args, **kwargs)
            with self.subTest(kind="synthetic OS link metadata"), patch.object(Path, "lstat", changed):
                self.reject(lambda: release.collect_payload(self.root))

    def test_export_never_overwrites_existing_destination_or_archive(self):
        self.destination.mkdir()
        preserved = self.destination / "keep.txt"
        write(preserved, "Keep this existing file.")
        self.reject(lambda: release.export_release(self.root, self.destination))
        self.assertEqual(preserved.read_text(), "Keep this existing file.")
        archive = self.base / "existing.zip"
        original = b"existing synthetic archive marker"
        write(archive, original)
        self.reject(lambda: release.export_release(self.root, self.base / "fresh", zip_path=archive))
        self.assertEqual(archive.read_bytes(), original)

    def test_archive_round_trip_and_content_tamper_detection(self):
        archive = self.archive()
        self.assertIsInstance(release.verify_archive(archive), dict)
        tampered = self.rebuild_zip(archive, transform=lambda name, body: body + b"\nmodified" if name == "src/example.py" else body)
        self.reject(lambda: release.verify_archive(tampered))

    def test_archive_rejects_extras_case_duplicates_traversal_and_symlink_metadata(self):
        archive = self.archive()
        for name in ("extra.txt", "../outside.txt", "SRC/EXAMPLE.PY"):
            with self.subTest(name=name):
                changed = self.rebuild_zip(archive, extras=[(name, b"extra")])
                self.reject(lambda: release.verify_archive(changed))
        changed = self.rebuild_zip(archive, modes={"src/example.py": stat.S_IFLNK | 0o777})
        self.reject(lambda: release.verify_archive(changed))

    def test_archive_manifest_cannot_claim_an_extra_unshipped_file(self):
        archive = self.archive()
        def extra_manifest(name, body):
            if name != "RELEASE_MANIFEST.json":
                return body
            value = json.loads(body)
            value["files"]["src/missing.py"] = {"sha256": "0" * 64, "bytes": 0}
            return json.dumps(value).encode()
        changed = self.rebuild_zip(archive, transform=extra_manifest)
        self.reject(lambda: release.verify_archive(changed))

    def test_archive_rejects_unlisted_comment_and_trailing_bytes(self):
        archive = self.archive()
        trailing = self.base / "trailing.zip"
        write(trailing, archive.read_bytes() + b"unlisted synthetic bytes")
        self.reject(lambda: release.verify_archive(trailing))
        commented = self.base / "commented.zip"
        write(commented, archive.read_bytes())
        with zipfile.ZipFile(commented, "a") as output:
            output.comment = b"unlisted synthetic comment"
        self.reject(lambda: release.verify_archive(commented))

    def staged_git(self, staged, calls):
        objects = {f"{i+1:040x}": (name, data) for i, (name, data) in enumerate(sorted(staged.items()))}
        def git(root, *args):
            calls.append(args)
            if args == ("ls-files", "--stage", "-z"):
                return b"".join(f"100644 {oid} 0\t{name}".encode() + b"\0" for oid, (name, _) in objects.items())
            if len(args) == 3 and args[:2] == ("cat-file", "-s"):
                return str(len(objects[args[2]][1])).encode() + b"\n"
            if len(args) == 3 and args[:2] == ("cat-file", "blob"):
                return objects[args[2]][1]
            raise AssertionError("Unexpected git command in staged-blob test")
        return git

    def staged_files(self):
        return {p.relative_to(self.destination).as_posix(): p.read_bytes()
                for p in self.destination.rglob("*") if p.is_file()}

    def test_clean_public_tree_staged_blobs_pass_without_a_real_git_repository(self):
        self.export()
        calls = []
        with patch.object(release, "_git", side_effect=self.staged_git(self.staged_files(), calls)):
            self.assertIsInstance(release.check_staged(self.destination), dict)
        self.assertTrue(any(args[:2] == ("cat-file", "blob") for args in calls))

    def test_malicious_staged_blob_is_rejected_even_when_working_file_is_safe(self):
        self.export()
        credential = "s" + "k-proj-" + "Z8x7C6v5B4n3" * 5
        staged = self.staged_files()
        staged["src/example.py"] = ("KEY = '" + credential + "'\n").encode()
        self.assertEqual((self.destination / "src/example.py").read_text(), "VALUE = 1\n")
        calls = []
        with patch.object(release, "_git", side_effect=self.staged_git(staged, calls)):
            self.reject(lambda: release.check_staged(self.destination), forbidden=credential)
        self.assertTrue(any(args[:2] == ("cat-file", "blob") for args in calls))

    def test_staged_private_policy_cannot_hide_behind_safe_working_policy(self):
        self.export()
        staged = self.staged_files()
        policy = json.loads(staged["public-release.json"])
        private_name = "." + "env"
        policy["files"].append(private_name)
        staged["public-release.json"] = json.dumps(policy).encode()
        staged[private_name] = b"synthetic private fixture"
        with patch.object(release, "_git", side_effect=self.staged_git(staged, [])):
            self.reject(lambda: release.check_staged(self.destination))


    def test_public_agent_guide_is_remapped_without_exporting_internal_instructions(self):
        write(self.root / "AGENTS.md", "Private workspace instructions must stay local.\n")
        public_text = "# Public agent guide\nUse the reviewed workflow skill.\n"
        write(self.root / release.PUBLIC_AGENT_GUIDE_SOURCE, public_text)
        self.files.append({"source": release.PUBLIC_AGENT_GUIDE_SOURCE, "target": "AGENTS.md"})
        self.policy()
        payload = release.collect_payload(self.root)
        self.assertEqual(payload["AGENTS.md"], public_text.encode())
        self.assertNotIn(b"Private workspace", payload["AGENTS.md"])
        archive = self.base / "source.zip"
        release.export_release(self.root, self.destination, archive)
        release.verify_archive(archive)
        self.assertEqual((self.destination / "AGENTS.md").read_text(), public_text)
        with patch.object(release, "_git", side_effect=self.staged_git(self.staged_files(), [])):
            self.assertEqual(release.check_staged(self.destination)["status"], "passed")

    def test_raw_or_arbitrary_internal_agent_guide_mappings_remain_blocked(self):
        for source, target in (("AGENTS.md", "AGENTS.md"), ("AGENTS.md", "docs/internal.md"),
                               ("src/example.py", "AGENTS.md"), ("CLAUDE.md", "AGENTS.md")):
            with self.subTest(source=source, target=target):
                self.policy(self.files + [{"source": source, "target": target}])
                self.reject(lambda: release.collect_payload(self.root))


if __name__ == "__main__":
    unittest.main()
