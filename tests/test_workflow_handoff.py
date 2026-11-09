"""The released handoff must have valid skill entrypoints and no missing links."""
import json
from pathlib import Path
import posixpath
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def payload_paths():
    policy = json.loads((ROOT / 'public-release.json').read_text(encoding='utf-8'))
    if policy['profile'] == 'source_workspace':
        return {entry['target']: ROOT / entry['source'] for entry in policy['files']}
    return {name: ROOT / name for name in policy['files']}


class WorkflowHandoffTests(unittest.TestCase):
    def test_skills_have_complete_scalar_frontmatter_and_no_unfinished_fields(self):
        from tools.install_workflow_skills import SKILL_NAMES
        for name in SKILL_NAMES:
            with self.subTest(skill=name):
                text = (ROOT / 'docs/public/skills' / name / 'SKILL.md').read_text(encoding='utf-8')
                match = re.match(r'\A---\n(.*?)\n---\n(.+)\Z', text, re.S)
                self.assertIsNotNone(match)
                fields = dict(line.split(': ', 1) for line in match[1].splitlines())
                self.assertEqual(set(fields), {'name', 'description'})
                self.assertEqual(fields['name'], name)
                self.assertRegex(name, r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
                self.assertLessEqual(len(name), 64)
                self.assertGreater(len(fields['description']), 30)
                self.assertNotIn(': ', fields['description'])
                self.assertNotIn('[TODO', text)
                self.assertGreater(len(match[2].strip()), 100)

    def test_relative_document_links_resolve_within_the_actual_export(self):
        paths = payload_paths()
        # The exporter creates these two files after collecting mapped sources.
        paths.update({name: ROOT / name for name in ('public-release.json', 'RELEASE_MANIFEST.json')})
        errors = []
        for target, source in paths.items():
            if not target.endswith('.md'):
                continue
            text = source.read_text(encoding='utf-8')
            # Only prose links count; examples inside fenced code are not links.
            text = re.sub(r'^```[^\n]*\n.*?^```\s*$', '', text, flags=re.M | re.S)
            for href in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', text):
                href = href.strip().strip('<>')
                url = urlsplit(href)
                if url.scheme or url.netloc or not url.path:
                    continue
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(target), unquote(url.path)))
                if resolved not in paths:
                    errors.append((target, href))
        self.assertEqual(errors, [], f'Missing released document links: {errors}')


if __name__ == '__main__':
    unittest.main()
