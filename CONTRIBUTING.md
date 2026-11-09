# Contributing

Keep changes small and explain the behavior and validation. Use synthetic shapes,
generic text and mocked service responses for tests. Do not contribute real
manuscripts, copyrighted panels, private generation prompts, production outputs,
research copies, credentials or personal information.

Install `requirements.txt`, configure an appropriately licensed Korean font,
and run `python -m unittest discover -s tests`. Unit tests must not make live
image-generation or Jev calls. Live verification is opt-in and separate.

Retain the MIT license and applicable third-party notices. Identify the source,
license and modifications for newly adapted code before adding it. Contributions
are offered under the project license unless explicitly agreed otherwise; do
not claim rights to third-party content you cannot grant.

New public files must be reviewed and explicitly added to `public-release.json`.
In a private production workspace, use source/target mappings and export a fresh
public tree. In a public source tree, update the target-path list. Do not widen
the manifest with wildcards or bypass path/secret checks to make CI green.

Before committing to the public repository, run
`python tools/public_release.py check --staged` after staging the exact change.
The check inspects index blobs rather than trusting clean working-tree copies.
It cannot remove already published history. See
[RELEASING](docs/public/RELEASING.md) for the export and review boundary.
