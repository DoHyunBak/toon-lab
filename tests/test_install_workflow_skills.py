"""Repository-local skill bootstrap must preserve existing work."""

import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.install_workflow_skills import SKILL_NAMES, _inside, _is_link, bootstrap_skills, main


class WorkflowSkillBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.payloads = {}
        for name in SKILL_NAMES:
            payload = f"---\nname: {name}\n---\nRead the repo workflow.\n".encode()
            self.payloads[name] = payload
            source = self.source(name)
            source.parent.mkdir(parents=True)
            source.write_bytes(payload)

    def source(self, name):
        return self.root / "docs/public/skills" / name / "SKILL.md"

    def destination(self, name):
        return self.root / ".agents/skills" / name / "SKILL.md"

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def make_link(self, target, link, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as exc:
            self.skipTest(f"symlink creation is unavailable: {exc}")

    def test_default_check_reports_exact_targets_and_never_creates_agents(self):
        before = self.snapshot()
        result = bootstrap_skills(self.root)
        self.assertEqual(result["mode"], "check")
        self.assertEqual(result["status"], "ready")
        self.assertEqual([item["name"] for item in result["skills"]], list(SKILL_NAMES))
        for item in result["skills"]:
            self.assertEqual(item["status"], "missing")
            self.assertEqual(item["source"], f"docs/public/skills/{item['name']}/SKILL.md")
            self.assertEqual(item["destination"], f".agents/skills/{item['name']}/SKILL.md")
        self.assertFalse((self.root / ".agents").exists())
        self.assertEqual(self.snapshot(), before)

    def test_install_copies_only_three_known_files(self):
        unrelated = self.root / "docs/public/skills/unrelated/SKILL.md"
        unrelated.parent.mkdir()
        unrelated.write_text("do not install")
        extra = self.source(SKILL_NAMES[0]).parent / "asset.png"
        extra.write_bytes(b"not part of bootstrap")
        result = bootstrap_skills(self.root, install=True)
        self.assertEqual(result["status"], "installed")
        for name in SKILL_NAMES:
            self.assertEqual(self.destination(name).read_bytes(), self.payloads[name])
        installed = list((self.root / ".agents").rglob("*"))
        self.assertEqual(sum(path.is_file() for path in installed), 3)
        self.assertFalse((self.root / ".agents/skills/unrelated").exists())

    def test_identical_install_is_noop_and_preserves_unrelated_destination_files(self):
        bootstrap_skills(self.root, install=True)
        extra = self.destination(SKILL_NAMES[0]).parent / "local-note.txt"
        extra.write_text("preserve")
        before = self.snapshot()
        mtimes = {name: self.destination(name).stat().st_mtime_ns for name in SKILL_NAMES}
        result = bootstrap_skills(self.root, install=True)
        self.assertEqual(result["status"], "already_current")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({name: self.destination(name).stat().st_mtime_ns for name in SKILL_NAMES}, mtimes)

    def test_late_conflict_fails_before_any_copy_and_preserves_existing_file(self):
        destination = self.destination(SKILL_NAMES[-1])
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"existing customized skill")
        before = self.snapshot()
        for install in (False, True):
            with self.subTest(install=install), self.assertRaisesRegex(ValueError, "conflicting.*preserved"):
                bootstrap_skills(self.root, install=install)
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(self.destination(SKILL_NAMES[0]).exists())

    def test_missing_last_source_prevents_all_mutation(self):
        self.source(SKILL_NAMES[-1]).unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "source is missing"):
            bootstrap_skills(self.root, install=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / ".agents").exists())

    def test_destination_symlink_to_outside_is_rejected_without_external_writes(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        self.make_link(outside, self.root / ".agents", directory=True)
        with self.assertRaisesRegex(ValueError, "symlinks/junctions"):
            bootstrap_skills(self.root, install=True)
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_file_symlink_even_inside_repo_is_rejected(self):
        source = self.source(SKILL_NAMES[0])
        source.unlink()
        self.make_link(self.source(SKILL_NAMES[1]), source)
        with self.assertRaisesRegex(ValueError, "symlinks/junctions"):
            bootstrap_skills(self.root, install=True)
        self.assertFalse((self.root / ".agents").exists())

    def test_destination_file_symlink_preserves_external_file(self):
        outside = Path(self.temporary.name) / "outside.md"
        outside.write_bytes(self.payloads[SKILL_NAMES[-1]])
        destination = self.destination(SKILL_NAMES[-1])
        destination.parent.mkdir(parents=True)
        self.make_link(outside, destination)
        with self.assertRaisesRegex(ValueError, "symlinks/junctions"):
            bootstrap_skills(self.root, install=True)
        self.assertEqual(outside.read_bytes(), self.payloads[SKILL_NAMES[-1]])
        self.assertFalse(self.destination(SKILL_NAMES[0]).exists())

    def test_parent_file_conflict_prevents_directory_creation(self):
        (self.root / ".agents").write_text("preserve")
        with self.assertRaisesRegex(ValueError, "not a directory"):
            bootstrap_skills(self.root, install=True)
        self.assertEqual((self.root / ".agents").read_text(), "preserve")

    def test_path_traversal_is_rejected_even_without_os_link_privileges(self):
        with self.assertRaisesRegex(ValueError, "inside the repository"):
            _inside(self.root, Path("../outside"))

    def test_reported_link_component_prevents_every_install_write(self):
        blocked = self.root / ".agents"
        with patch("tools.install_workflow_skills._is_link", side_effect=lambda path: path == blocked):
            with self.assertRaisesRegex(ValueError, "symlinks/junctions"):
                bootstrap_skills(self.root, install=True)
        self.assertFalse(blocked.exists())

    def test_windows_reparse_attribute_is_treated_as_a_link(self):
        with patch("pathlib.Path.lstat", return_value=SimpleNamespace(st_mode=0o040755, st_file_attributes=1024)):
            with patch("tools.install_workflow_skills.stat.FILE_ATTRIBUTE_REPARSE_POINT", 1024, create=True):
                self.assertTrue(_is_link(self.root))

    def test_cli_default_and_check_are_readonly_install_is_explicit(self):
        with patch("tools.install_workflow_skills.bootstrap_skills", return_value={}) as bootstrap:
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main([]), 0)
                bootstrap.assert_called_with(install=False)
                self.assertEqual(main(["--check"]), 0)
                bootstrap.assert_called_with(install=False)
                self.assertEqual(main(["--install"]), 0)
                bootstrap.assert_called_with(install=True)

    def test_cli_conflict_returns_nonzero(self):
        with patch("tools.install_workflow_skills.bootstrap_skills", side_effect=ValueError("conflict")):
            with patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(main(["--install"]), 1)


if __name__ == "__main__":
    unittest.main()
