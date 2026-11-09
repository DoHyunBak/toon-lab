# Upstream attribution and extraction notes

Reference: [ahmet360/manga-studio](https://github.com/ahmet360/manga-studio)

Pinned checkout: `2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4` (2026-10-16 inspection).
In the development workspace, `vendor/manga-studio` retains the upstream repository
and its complete LICENSE. This checkout is excluded from the source-only release;
the notice below is retained for the adapted source modules.
No upstream scripts were executed. Application modules do not import vendor code.

Adaptation map:

- `src/comfy_client.py`: adapted the core checkpoint → character LoRA chain → CLIP conditioning → sampler → VAE decode → SaveImage graph from `comfy_workflow.py::build_workflow`; adapted urllib queue/history/upload/view operations from `generate.py::ComfyClient`. Added guide ControlNet chains, strict base-template injection, preflight, explicit output selection and failure handling. Omitted LLM/story generation, studio UI, cloud/GPU orchestration, hires/detailer and custom-node pipelines.
- `src/bubble_renderer.py`: adapted `bubbles.py` balloon/tail/shout/cloud/caption geometry and measured wrapping approach. Replaced space-only wrapping and silent fallback with Unicode-aware fitting, Korean font verification, normalized coordinates and collision errors.
- `src/webtoon_stitcher.py`: adapted `assemble_pages.py::assemble_page` Pillow canvas/paste/save sequence. Replaced fixed-height grid, center crop and missing-panel placeholder with aspect-preserving ordered cuts, whitespace and gutter-only lossless slicing.
- `src/script_formatter.py`: independently written TXT/JSON adapter, referencing upstream parser structure and the external tool's published native grammar. It does not copy upstream automatic story generation or infer new story content.

Upstream source links pinned to the inspected version:

- [comfy_workflow.py](https://github.com/ahmet360/manga-studio/blob/2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4/comfy_workflow.py)
- [generate.py](https://github.com/ahmet360/manga-studio/blob/2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4/generate.py)
- [bubbles.py](https://github.com/ahmet360/manga-studio/blob/2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4/bubbles.py)
- [assemble_pages.py](https://github.com/ahmet360/manga-studio/blob/2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4/assemble_pages.py)

## MIT License (upstream)

Copyright (c) 2026 ahmet360

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Source-only release boundary

The project MIT license covers the project contributions in the distributed
source, public documentation and generic test/example fixtures. It does not
replace the upstream copyright and permission notice above. Retain this file
when redistributing the adapted modules.

The source-only release does not bundle private manuscripts, story-specific
production scripts, reference artwork, other generated artwork, research or audit
records, credentials, vendor checkouts, fonts, model weights or a Python runtime.
The README includes one toon_lab showcase excerpt, outside the software's MIT license.
See [License scope](docs/public/LICENSE_SCOPE.md) for the boundary between the
software and user-supplied materials or external services.

## Separately installed dependencies and services

- Pillow is installed separately through `requirements.txt`. Its MIT-CMU license
  and notices for bundled components remain applicable to that dependency.
  This source-only release does not redistribute Pillow wheels or `.venv`.
  If you distribute a runtime or binary bundle, review and retain its actual
  dependency notices. See [Pillow licensing](https://pillow.readthedocs.io/en/stable/about.html#license).
- Font binaries are not bundled. Supply a font whose license permits your use.
  For example, redistributing a Pretendard font requires its applicable SIL OFL
  notice and conditions; using a font and redistributing its binary are separate
  actions. See [Pretendard v1.3.9 license](https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/LICENSE).
- TypeSafe/Jev and image-generation providers are external services. The MIT
  license of this client code does not supply an API account, credits, service
  rights or a model-weight license. The optional TypeSafe agent skill has its
  own MIT notice and is not bundled in this source-only release. Its license
  does not replace the [TypeSafe customer agreement](https://typesafe.ai/legal/mca).
- ComfyUI checkpoints, LoRAs, ControlNet models and other optional resources are
  not bundled. Check the conditions of the particular resources you supply;
  this project's license does not grant rights to them.
