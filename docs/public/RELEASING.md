# Preparing a source-only release

The production workspace and the public source tree are different publication
boundaries. Export reviewed files into a **new isolated directory**. Do not
initialize or publish the production workspace as the public repository, and
do not ZIP the whole working directory. Do not copy its existing Git history.

## Build the reviewable result

Run from the source root using its Python environment:

```sh
python tools/public_release.py check
python tools/public_release.py export --output-dir dist/toon_lab-public --zip dist/toon_lab-source.zip
python tools/public_release.py verify-zip dist/toon_lab-source.zip
```

Destinations must be new. Use a fresh output name for later builds; the exporter
does not overwrite an existing directory or archive. It never needs a model key,
live model call, GitHub access or production data upload. Local known credential
values may be read in memory to test the selected payload, never to publish them.

`public-release.json` is an exact allowlist. In the private workspace it maps
reviewed sources to public target paths; for example, the dedicated public README
becomes the exported root README. In the public tree the policy contains target
paths only. The exporter generates `RELEASE_MANIFEST.json` with payload sizes and
SHA-256 hashes. That manifest establishes file identity, not author identity,
creation time, license ownership or an independent legal audit.

The exported `.env.example` also comes from a separate reviewed placeholder
template, not a developer's local configuration/example file. Never assume a
file is safe to publish merely because its name ends in `.example`.

The root `AGENTS.md` is remapped only from the independently authored
`docs/public/REPO_AGENT_GUIDE.md`. The production workspace's original root
instructions remain blocked as a source. The three workflow skills are delivered
as reviewed Markdown under `docs/public/skills/`; their optional installer copies
only those three files to ignored, repo-local `.agents/skills/`. It does not export
the private workspace's skill catalog, touch user-global settings, or replace
conflicting installed instructions. New skills need their own exact manifest entry.

The only `workspace/` files in this release are two explicitly reviewed generic
JSON examples required by the offline demo/protocol tests. The README showcases
one reviewed PNG, pinned to its SHA-256 in the release validator. Reference images,
other story assets, research and production/audit records stay private. Production-specific
scripts and private tests are also omitted even though their extensions are code.

Inspect the archive's exact paths and the exported public README/license/notices.
Review that upstream MIT terms remain intact. Confirm that no service accounts,
font binaries, model weights or private content were added. ZIP verification
rejects unsafe names, duplicates, linked entries, unexpected payloads and hash
mismatches without extracting untrusted paths.

## Verify the isolated tree

Install dependencies in an environment outside the release payload, change to
the exported directory and run:

```sh
python tools/setup_open_fonts.py
python -m unittest discover -s tests
python tools/public_release.py check
```

The tests must work without the production workspace, its references or its
private legal/research modules. Tests and the offline demo do not call live
model services. Korean lettering tests require a suitable local font.

The default `doctor` checks local text-only prerequisites without reading an
image-reference catalog. An explicitly requested reference-catalog check verifies
its actual originals. Never copy a private library merely to obtain a ready result.
Doctor does not contact ComfyUI or execute a GPU graph; test those separately.

## GitHub publication boundary

This setup does not create a repository, commit, push, PR or public GitHub Release.
When publication is explicitly authorized, use only the reviewed exported tree
and a fresh, appropriate repository/history. Stage the intended public files and
run `python tools/public_release.py check --staged`. A source-workspace profile is
not accepted as the staged public tree. Inspect the staged diff and paths again.

`check --staged` checks actual index blobs, names, policy and credential rules;
it does not require current content hashes in an optional stored release manifest.
Exact manifest-to-byte integrity is enforced by `verify-zip` on a newly exported
archive. Always make a fresh export after source changes.

Before publication, enable the available GitHub secret-scanning/push-protection
features, private vulnerability reporting and branch/ruleset checks appropriate
to the repository/account. Repository-side settings cannot be enabled before the
repository exists. The included CI has read-only permissions, pinned action
commits and no publishing step; its actual GitHub run must be checked later.

The workflow tests an isolated export, checks its ZIP and audits dependencies.
Dependabot configuration proposes dependency/action updates; it does not grant
automatic merge or release permission. Keep human review on manifest, workflow,
license and publication changes. No self-check can protect against a maintainer
deliberately bypassing or weakening the boundary.

After any source, dependency, notice or allowlist change, rebuild and recheck the
release. Do not describe an earlier snapshot's test or scan result as verification
of a newly modified archive.
