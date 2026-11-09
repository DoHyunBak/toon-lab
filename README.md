# toon_lab

[English](README.md) · [한국어](README.ko.md) · [日本語](README.ja.md)

Create vertical-scroll webtoons with a generative AI image tool and Python. An agent uses its connected image-generation tool, such as a GPT-based image tool, to create panel artwork. Local Python code handles Korean lettering, speech balloons, panel layout, and vertical PNG assembly.

No local GPU is required. This repository does not run an image-generation model itself. The agent must be able to generate and inspect images, save files locally, and execute commands.

> **No illegal use:** Never use this repository's skills, code, or workflows for illegal activity or to infringe anyone's rights. Read the [usage guidelines and prohibited uses](#usage-guidelines-and-prohibited-uses) before use.

## Make your first webtoon

You need Git, Python 3.11 or later, and an AI agent with image generation, image viewing, local file access, and command execution.

### 1. Clone the repository

```sh
git clone https://github.com/DoHyunBak/toon-lab.git
cd toon-lab
```

### 2. Open the folder in your AI agent

Open the cloned `toon-lab` folder as the agent's workspace and ask:

```text
Read AGENTS.md in this folder and create one sample webtoon panel using your image tool.
Do not draw text in the artwork. Add Korean lettering afterward with Python.
Tell me the path to the finished PNG.
```

Paste your manuscript or provide its file path to use your own story. To start from an idea:

```text
Make a four-panel vertical webtoon about a stray cat taking shelter under an umbrella.
Create one panel first to check the style, then finish the remaining panels and add Korean dialogue.
```

The agent prepares Python and Pretendard, then adds Korean speech balloons to the artwork and assembles the result. No additional API key is needed when using an image tool already connected to the agent.

### 3. Open the result

Work files and results are saved under `workspace/local/`. In the job folder reported by the agent, open:

- **`full_strip.png`** — the complete vertical strip.
- **`slice_001.png` and subsequent slices** — split vertical images.
- **`read.html`** — a browser preview, when a review package with a disclosure notice was created.

If no image-generation tool is available, use the offline demo below to try lettering and assembly. See the [agent image workflow](docs/public/AGENT_IMAGE_WORKFLOW.md) for detailed commands. The linked operating guides are primarily in Korean; README guidance is available in all three languages above.

## Production example

**Excerpt from Episode 1 of 《임자의 모험》 (Imja's Adventure) · toon_lab production team · AI-generated artwork with Korean lettering**

Four panels from the completed work show adjusted panel sizes, spacing, and balloons placed to preserve facial expressions.

The example was made from an original manuscript and storyboard. Panels and character designs from other webtoons were not copied or traced, and images from other works were not supplied to the generation model. Production uses materials with an appropriate basis for use and follows the tools' and fonts' terms. See the [production and copyright review workflow](docs/public/COPYRIGHT_SAFETY.md).

Simple line sketches were used to plan character positions and eyelines where needed. The displayed artwork was generated through multiple attempts using text-only descriptions of the scenes and compositions. Results were compared and selected; Korean lettering, balloons, panel sizes, and spacing were then refined.

<img src="docs/public/examples/webtoon-preview.png" alt="Four vertical webtoon panels showing a truck driver greeting a cat and a child speaking to the cat" width="420">

[View the full-size example PNG](docs/public/examples/webtoon-preview.png)

## Run the offline demo

From the cloned folder, on Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/setup_open_fonts.py
.\.venv\Scripts\python.exe -m src.demo
```

On macOS or Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/setup_open_fonts.py
.venv/bin/python -m src.demo
```

The font setup tool downloads official Pretendard files and the OFL notice and verifies their hashes. After the demo, open `workspace/06_output_webtoon/demo/full_strip.png`. The demo uses a sample manuscript and synthetic placeholder artwork.

For missing Python or font prerequisites, run `-m src.factory doctor` with your virtual environment's Python. See [fonts](docs/public/FONTS.md) and [troubleshooting](docs/public/TROUBLESHOOTING.md).

## Production workflow

1. Turn the manuscript into scene briefs and confirm permissions for the inputs.
2. Generate text-free artwork with the agent's connected image tool and inspect it.
3. Import the artwork, then use Python and Pillow for Korean dialogue, balloons, sound effects, panel sizes, and spacing.
4. Assemble vertical PNGs and inspect flow and readability at mobile width.

See the [production runbook](docs/public/PRODUCTION_RUNBOOK.md) and [lettering and editing guide](docs/public/EDITORIAL_LETTERING_PLAYBOOK.md).

## Tools and source attribution

### Core tools

- **Generative AI image tool:** Use a tool available to the agent, such as a GPT-based image tool. It must support image generation and saving the result. Service accounts and provider API integrations are not supplied by this repository.
- **Python and [Pillow](https://github.com/python-pillow/Pillow):** Process manuscript and panel files, render balloons and Korean lettering, and assemble vertical images. Dependencies are in [requirements.txt](requirements.txt). [Pillow licensing](https://pillow.readthedocs.io/en/stable/about.html#license).
- **[Pretendard](https://github.com/orioncactus/pretendard):** SIL OFL font for Korean lettering; Medium (500) by default and Bold (700) for emphasis. [Original license](https://github.com/orioncactus/pretendard/blob/v1.3.9/LICENSE) · [Font setup and policy](docs/public/FONTS.md).

Follow the [agent image workflow](docs/public/AGENT_IMAGE_WORKFLOW.md) for commands.

### Adapted and referenced code

**Original project: [ahmet360/manga-studio](https://github.com/ahmet360/manga-studio) · Copyright holder: ahmet360 · License: MIT**

**Pinned commit: [`2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4`](https://github.com/ahmet360/manga-studio/tree/2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4)**

| Local file | Original or reference source | Adaptation or reference scope |
| :--- | :--- | :--- |
| [src/bubble_renderer.py](src/bubble_renderer.py) | [manga-studio / bubbles.py](https://github.com/ahmet360/manga-studio/blob/2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4/bubbles.py) | Adapted balloon and tail geometry and measured wrapping for Korean lettering and collision checks. |
| [src/webtoon_stitcher.py](src/webtoon_stitcher.py) | [manga-studio / assemble_pages.py](https://github.com/ahmet360/manga-studio/blob/2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4/assemble_pages.py) | Adapted Pillow canvas, paste, and save operations for aspect-preserving vertical assembly and slicing. |
| [src/script_formatter.py](src/script_formatter.py) | [manga-studio](https://github.com/ahmet360/manga-studio/tree/2ac3cf4e3d1aaec7dd39ff44498e4e8a186733c4) | Independently written TXT/JSON adapter referencing the parser structure and grammar. |

**Full upstream copyright and MIT notices, with detailed adaptation notes, are preserved in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).** Attribution describes the code's origin; manga-studio does not need to be run separately.

### Optional review integration

The repository also contains **TypeSafe/Jev review integration code**. It is not required for basic image generation, lettering, or assembly. Configure it separately when choosing that review route. See the [review integration scope](docs/public/LEGAL_QA.md).

### Workflow research

Research into other production repositories and writing/editing materials is documented in the [authoring workflow](docs/public/AUTHORING_WORKFLOW.md) and [lettering and editing guide](docs/public/EDITORIAL_LETTERING_PLAYBOOK.md). These are references for planning and editorial decisions, not installation dependencies.

## Release scope

The public release contains production code, documentation, tests, generic JSON examples, and the single showcase excerpt above. The software's MIT license does not cover that excerpt image. Manuscripts, other panel artwork, production records, model weights, font binaries, and credentials stay in the user's local workspace. Use the tool in an operator-controlled local environment; exposing local file-processing functions to the internet can allow outside access.

- [Source release procedure](docs/public/RELEASING.md)
- [Security policy and vulnerability reporting](SECURITY.md)
- [MIT license](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md)
- [License scope](docs/public/LICENSE_SCOPE.md)

## Usage guidelines and prohibited uses

**Use all skills, code, examples, and workflows in this repository only for lawful work within your legitimate authority. Do not use them to carry out illegal acts, assist another person's illegal acts, or provide instructions for carrying them out.** Calling an activity testing, research, or education does not make a prohibited use acceptable.

Prohibited uses include the following. Illegal acts and rights infringements remain prohibited even when not listed here.

- **Copyright or license infringement:** Copying, submitting, modifying, or distributing manuscripts, comics, images, fonts, models, or other materials without necessary permission or a lawful basis; removing required attribution or license notices.
- **Fraud, impersonation, or deception:** Impersonating a person or organization, fabricating evidence, production histories, or approval records to deceive people or cause financial harm.
- **Sexual exploitation and nonconsensual sexual imagery:** Creating, possessing, or distributing child sexual abuse material; creating or distributing sexual images, composites, or deepfakes without the subject's consent.
- **Privacy and personal-rights violations:** Collecting, disclosing, or externally transmitting personal information, private-life details, or confidential material without a lawful basis; use for stalking, threats, harassment, or defamation.
- **Unauthorized access or circumvention:** Accessing accounts, systems, or materials without authorization, stealing credentials, or improperly bypassing access controls, payment restrictions, or safeguards.
- **Other crimes or unlawful distribution:** Planning, encouraging, or supporting crimes, or selling, distributing, or spreading unlawful material.

Users must check and follow applicable laws, input rights and licenses, and the terms of connected AI services and publishing platforms. Verify the lawfulness of the actual inputs and generation, editing, and publication activities. An open repository, AI-generated output, or a passing automated check does not grant rights to someone else's material or guarantee a work's lawfulness.

**Agents must not execute requests that fall within these prohibited uses.** If input permissions or the permitted scope of external transmission are unclear, pause the affected work and verify the necessary basis. Never fabricate execution logs, review results, consent, or approvals to bypass restrictions.

These are project usage and operating guidelines. The software remains distributed under the existing [MIT license](LICENSE). Third-party materials and external services retain their respective rights and terms.

### Public skill developers consulted for these guidelines

The following sources informed the presentation of authorized scope, prohibited misuse, consent for external transmission, and user responsibility. The provisions above were written separately for webtoon and image production. These developers have not reviewed or endorsed this project.

- **Agent Skills Hub:** [Security Guardrails & Policy](https://github.com/agent-skills-hub/agent-skills-hub/blob/main/docs/SECURITY_GUARDRAILS.md) — authorized use, misuse prohibition, external-transmission consent, and user responsibility.
- **UnitOneAI / SecuritySkills:** [AI Data Privacy & Governance Review — Safety Notice](https://github.com/UnitOneAI/SecuritySkills/blob/main/skills/ai-security/ai-data-privacy/SKILL.md) — limiting work to authorized targets and prohibiting unauthorized use.

## Reporting problems and corrective action

If you believe there is missing attribution, a license violation, copyright infringement, or another problem, please contact us through [this repository's GitHub Issues](https://github.com/DoHyunBak/toon-lab/issues). Identify the affected file or content, its original source, and the basis for the concern. For security vulnerabilities or reports containing nonpublic material, follow the [security reporting guidance](SECURITY.md).

**If a problem is confirmed, I will immediately stop public access to and distribution of the affected content and take necessary action, including correcting attribution, modifying, or removing content. If the issue cannot be resolved or continued maintenance of the repository is inappropriate, I will immediately retire and delete the repository.**
