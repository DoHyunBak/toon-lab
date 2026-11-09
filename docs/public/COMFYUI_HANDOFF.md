# ComfyUI 제작 인계

이 저장소는 원고 준비, ComfyUI 실행 연동, B/C 말풍선, 장면 배치, 세로 조립, 검수와 증빙을 재사용하는 소스 묶음이다. 원고·캐릭터 원화·생성 이미지·폰트·모델 가중치·개인 검수 기록·인증정보는 포함하지 않는다. 실제 작품을 이어 만들려면 소유자가 제공하는 비공개 입력과 해당 이용 범위가 필요하다.

처음 받은 에이전트는 [AGENT_START](AGENT_START.md)를 먼저 읽는다. 아래 절차는 환경과 실행을 재현하는 방법이다. 문서, 모의 테스트, 서버 접속만으로 GPU 생성·작화 유지·작품 검수가 완료된 것은 아니다.

공식 설치/API 문서 확인일은 2026-10-31이다. 설치·CLI·노드 계약이 바뀌면 연결된 공식 문서와 실제 checkout을 다시 확인한다.

## 1. 먼저 고정할 것

- 작업 범위, 승인된 원고의 장면 ID와 순서, 캐릭터 설정, 컷별 목표를 확인한다. 예제 원고는 형식 시험용이며 본편으로 바꾸지 않는다.
- 생성 입력 모드를 기록한다. `text_only`는 모든 이미지 입력을 제외한다. 별도 허용된 자체 원화 참조 작업은 허용된 이미지·행위·모델/수신자·개수와 해시를 특정한다. 기존 작업의 모드나 실제 사용 이력을 소급 수정하지 않는다.
- 이번 실행에서 사용하는 모델, 그래프, 노드, 폰트와 외부 서비스를 정한다. 설치 가능 여부와 상업 이용·재배포·모델 입력 허용은 서로 다른 확인 사항이다.
- 완료 조건을 환경 확인, 한 컷 실제 생성, 원화 검수, 식자/배치 검수, 전달본, 기록 적재로 나누어 적는다. 각 단계의 미실행 항목을 남긴다.

## 2. 환경을 분리해서 설치

저장소 루트에서 toon_lab 후처리 환경을 만든다. 다음은 Windows PowerShell 예시다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.factory doctor
```

Linux/macOS에서는 `.venv/bin/python`을 사용한다. 한글 식자는 사용 권한이 있는 한글 폰트가 필요하다. `WEBTOON_FONT` 또는 해당 명령의 `--font`로 로컬 폰트를 지정한다. 폰트 파일은 저장소에 넣지 않는다.

ComfyUI는 **별도의 설치 경로와 Python 환경**을 사용한다. toon_lab의 `.venv`에 ComfyUI의 torch/custom node 의존성을 섞지 않는다. 먼저 OS, GPU 종류, 드라이버, VRAM, 여유 디스크를 확인하고 [공식 설치 문서](https://docs.comfy.org/installation/manual_install)와 [하드웨어 요구사항](https://docs.comfy.org/installation/system_requirements)에 맞는 방법을 선택한다.

- Windows Portable: GPU에 맞는 공식 배포본과 내장 `python_embeded`를 사용한다. 별도 설치나 업데이트는 그 Python에 적용한다. [Portable 안내](https://docs.comfy.org/installation/comfyui_portable_windows)
- 수동 설치: 별도 가상환경에 공식 ComfyUI 저장소를 설치하고, 해당 하드웨어에 맞는 PyTorch와 ComfyUI `requirements.txt`를 설치한다. NVIDIA/CUDA, AMD/ROCm, Intel/XPU, Apple/MPS 명령을 서로 바꾸어 쓰지 않는다.
- Desktop: 지원 하드웨어와 해당 버전의 설치 안내를 따른다. 환경 복제에는 [Desktop snapshot](https://docs.comfy.org/installation/desktop/usage/snapshots)을 활용할 수 있다. snapshot에도 노드 URL, 설치 경로 등 비공개 정보가 있는지 확인한 뒤 공유한다.

ComfyUI 버전, Git commit 또는 배포 파일명, Python/PyTorch 버전, GPU/드라이버, 실행 명령을 비공개 실행 기록에 남긴다. 이 문서의 특정 설치 명령을 영구적인 최신값으로 보지 말고 변경 시 공식 문서를 다시 확인한다.

서버는 기본적으로 `http://127.0.0.1:8188`에서 사용한다. 외부 공개나 `--listen 0.0.0.0`을 설정의 필수 단계로 추가하지 않는다. 원격 서버 사용은 자료 전송 대상과 허용 범위를 별도로 확인한다.

공식 `comfy-cli`를 추가로 쓰는 경우에는 로컬 작업에 `--where local`을 명시한다. 현재 CLI는 로그인 상태에 따라 Cloud로 라우팅할 수 있으며 `comfy generate`는 partner API 경로다. 이를 로컬 모델 실행으로 기록하지 않는다. [공식 CLI 안내](https://docs.comfy.org/agent-tools/cli)

### 예정 대상: Windows + NVIDIA GeForce RTX 5060

이 인계의 예정 GPU는 RTX 5060이며 실제 장착 모델·VRAM·드라이버와 GPU 실행은 아직 확인하지 않았다. RTX 5060 계열은 Blackwell 기반이다. 데스크톱/노트북/다른 variant를 이름으로 추정하지 말고 대상 PC에서 확인한다. [NVIDIA 제품 정보](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5060-family/)

```powershell
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

우선 현재 공식 Windows Portable의 **현대 NVIDIA GPU용 배포본**을 선택한다. 확인일 기준 공식 안내는 CUDA 13.0/Python 3.13 배포본을 현대 RTX용으로 구분하며, 구형 GPU용 cu126 배포본을 별도로 둔다. RTX 5060에 오래된 cu126 해결책을 그대로 적용하지 않는다. [ComfyUI Portable](https://docs.comfy.org/installation/comfyui_portable_windows)

수동 설치는 현재 [공식 PyTorch 설치 선택기](https://pytorch.org/get-started/locally/)의 Windows/CUDA 조합과 ComfyUI 지침을 함께 확인한다. PyTorch 2.12 발표는 Blackwell에 CUDA 13.0 이상 wheel을 안내하며 Windows driver 580.88 이상 조건을 명시한다. 이것은 해당 발표의 최소 조건이므로 설치 시점의 최신 지원 조건과 실제 드라이버를 다시 확인한다. [PyTorch 2.12 안내](https://pytorch.org/blog/pytorch-2-12-release-blog/)

Portable 루트에서 다음 probe를 실행해 실제 사용되는 torch 환경을 기록한다. 수동 설치라면 그 ComfyUI 환경의 Python으로 바꾼다. 이는 작은 CUDA 연산 시험이며 이미지 생성 시험과 별개다.

```powershell
.\python_embeded\python.exe -c "import torch; print(torch.__version__, torch.version.cuda); assert torch.cuda.is_available(), 'CUDA unavailable'; print(torch.cuda.get_device_name(0), torch.cuda.get_device_properties(0).total_memory, torch.cuda.get_device_capability(0)); print(torch.ones(1, device='cuda').cpu().tolist()); torch.cuda.synchronize()"
```

VRAM 실제값과 다른 앱의 점유량을 기록한 뒤 적합한 모델·정밀도·해상도를 선택한다. batch=1, 한 컷, 필요한 최소 노드로 시작하며 처음부터 여러 LoRA·ControlNet·업스케일을 결합하지 않는다. OOM이면 실제 로그와 메모리를 확인하고 한 조건씩 바꿔 시험한다. 특정 작화 모델 자동 다운로드, SDXL 품질 보장, 모든 OOM 해결 완료를 이 준비 문서로 주장하지 않는다.

## 3. 모델과 custom node를 잠근다

모델 가중치를 Git에 넣거나 미확인 모델을 자동 다운로드하지 않는다. 사용할 각 파일에 다음 정보를 실제 확인값으로 기록한다.

- 모델명·variant·모델 계열, 원 제공자와 다운로드 URL, 정확한 파일명과 ComfyUI 하위 폴더.
- 라이선스 URL·확인일·상업 이용/생성 입력/배포 조건, 필요한 고지와 미확인 사항.
- 원 제공자의 revision이 있으면 그 값, 다운로드한 실제 파일의 바이트 수와 SHA-256.
- 조합되는 checkpoint/diffusion model, text encoder, VAE, LoRA, ControlNet 등의 호환 관계.

다음 명령은 다운로드된 파일의 식별값을 확인한다. 해시 일치가 라이선스나 학습 데이터의 적법성을 증명하지는 않는다.

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'D:\models\YOUR_MODEL.safetensors'
```

모델은 공유 저장 경로를 두고 `extra_model_paths.yaml`로 연결하면 중복 복사를 줄일 수 있다. Portable/수동 설치는 ComfyUI 루트의 `extra_model_paths.yaml.example`을 참고한다. Desktop은 Storage 설정 또는 해당 앱의 `extra_models_config.yaml`을 사용한다. 기존 경로 설정을 덮어쓰지 말고 변경 후 서버를 재시작한다. [공식 모델 경로 설정](https://docs.comfy.org/installation/comfyui_portable_windows)

custom node가 필요하면 먼저 source와 기능, 라이선스, 설치 스크립트를 확인한다. registry ID+version 또는 repository URL+commit을 잠그고 그 노드의 의존성을 **ComfyUI가 실제 사용하는 Python**에 설치한다. 재시작 로그의 `import failed`와 `/object_info`의 class 존재 여부를 확인한다. 노드 설치만으로 필요한 모델까지 준비됐다고 판단하지 않는다. [공식 custom node 설치](https://docs.comfy.org/installation/install_custom_node)

작동하는 조합을 확보한 뒤 ComfyUI commit, 노드 버전, pip 패키지 버전과 모델 목록을 함께 보존한다. 버전 없는 `latest`, 누락된 해시, 실제 시험하지 않은 조합은 잠금 완료로 표시하지 않는다. ComfyUI 본체와 각 노드·모델의 라이선스는 이 저장소의 MIT와 별개다. [ComfyUI 라이선스](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE)

## 4. 두 실행 경로를 구분한다

### 제한된 SD1.5/SDXL 어댑터

`src.comfy_client`는 컷 JSON에서 core-node 그래프를 만드는 기존 어댑터다. `docs/public/templates/comfy_config.example.json`과 `workspace/workflow_api.example.json`을 참고하되, 실제 설정은 무시되는 로컬 작업 경로에 둔다.

```powershell
.\.venv\Scripts\python.exe -m src.comfy_client --help
.\.venv\Scripts\python.exe -m src.comfy_client workspace/local/episode.json --characters workspace/local/characters.json --config workspace/local/comfy.json --output-dir workspace/local/comfy_dryrun_v1 --dry-run
.\.venv\Scripts\python.exe -m src.comfy_client workspace/local/episode.json --characters workspace/local/characters.json --config workspace/local/comfy.json --output-dir workspace/local/comfy_run_v1 --check
```

위 파일은 사용자가 별도로 준비하는 입력 경로 예시다. `--dry-run`은 서버를 호출하지 않고 계획/그래프를 쓴다. `--check`는 GET preflight만 수행하며 업로드하거나 큐에 넣지 않는다. 실제 생성은 같은 입력에서 `--check`를 생략하면 시작된다. 실행 전에 한 컷만 포함한 별도 원고로 범위를 줄인다.

두 ComfyUI 실행 경로는 기본적으로 루프백 서버에만 연결하며 HTTP 리디렉션과 시스템 프록시를 사용하지 않는다. 외부 서버를 사용하려면 `--allow-remote`가 필요하다. 외부 서버에 연결하기 전에 대상 주소와 회차의 가이드 파일 경로를 확인하고, 전송이 허용된 입력에만 HTTPS 또는 신뢰할 수 있는 전용 연결을 사용한다.

이 어댑터의 base template은 `CheckpointLoaderSimple`, `CLIPTextEncode` 두 개, `EmptyLatentImage`, `KSampler`, `VAEDecode`, `SaveImage`의 7노드 API JSON이다. 어댑터가 선택적으로 LoRA와 ControlNet 노드를 추가할 수 있지만 임의 custom graph를 읽는 기능은 아니다. UI의 `nodes/links` JSON, Flux/Anima 및 별도 구조가 필요한 모델, IPAdapter/이미지편집 그래프를 이 경로에 억지로 넣지 않는다. `model_family` 선언은 실제 모델 파일 분석이나 품질 보증이 아니다.

ControlNet 경로가 있다는 사실은 현재 작품에 이미지 입력이 허용됐다는 뜻이 아니다. 자체 스타일 원화 한 장을 받는 경로와 pose/lineart/depth guide는 서로 다르다. 승인된 스타일을 유지하려면 모델·그래프 선택 뒤 실제 비교 검수를 거쳐야 한다.

### ComfyUI에서 만든 임의 API 그래프

모델에 맞는 그래프를 ComfyUI native UI에서 구성하고 작동을 확인한 뒤 편집용 workflow와 **API export JSON**을 각각 보존한다. 현재 공식 예제는 `File → Export (API)`로 실행용 그래프를 내보내도록 안내한다. [공식 API 예제](https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/basic_api_example.py)

API 그래프 실행에는 `src.comfy_runner`를 사용한다. 실제 옵션은 체크아웃의 `--help`를 기준으로 한다.

```powershell
.\.venv\Scripts\python.exe -m src.comfy_runner --help
.\.venv\Scripts\python.exe -m src.comfy_runner workspace/local/workflow_api.json --output-dir workspace/local/native_run_v1 --check
.\.venv\Scripts\python.exe -m src.comfy_runner workspace/local/workflow_api.json --output-dir workspace/local/native_run_v1 --execute
```

`--check`는 `/system_stats`와 `/object_info`를 GET으로 조회하며 파일 작성, 업로드, 큐 제출을 하지 않는다. `--execute`는 새 output-dir을 요구하고 실행 그래프 원본을 `workflow_api.json`, 실행 상태를 `receipt.json`, 선택한 출력 이미지를 `image.png`로 보존한다. 큐 POST는 한 번만 시도한다.

runner는 `SaveImage`가 정확히 하나 있는 그래프를 사용하고 그 노드에서 생성된 이미지 한 개의 PNG만 받는다. `PreviewImage`를 함께 두는 것은 가능하지만 여러 `SaveImage`나 batch 결과 여러 개를 선택/수집하는 기능은 없다. 필요하면 그래프를 한 컷 출력으로 나눈다. 서버는 `--server`로 지정할 수 있으며 비-loopback URL은 `--allow-remote`를 명시해야 한다. 이 옵션은 자료 전송 허가를 대신하지 않는다. 대기 설정은 `--timeout`, `--http-timeout`, `--poll-interval`의 실제 `--help`를 따른다.

여기서 임의 그래프는 해당 ComfyUI 서버에 설치되어 실행 가능한 API 그래프라는 뜻이다. runner가 노드·모델을 설치하거나 누락된 이미지를 만들어 주지는 않는다. `LoadImage` 등 입력은 서버가 참조할 수 있도록 별도 준비하고, 실제 사용한 원본/서버 파일명·해시·업로드 여부를 기록한다. Cloud/API/네트워크 노드를 넣으면 로컬 서버에서 실행하더라도 외부 전송이 발생할 수 있으므로 그래프의 모든 노드와 수신자를 확인한다.

생성 전에 `/object_info`로 노드/모델 입력을 확인하고 `/system_stats`로 실제 장치를 확인한다. `POST /prompt`의 prompt_id와 실행 그래프 해시를 보존한다. 이후 `/history/{prompt_id}`에서 해당 실행 결과를 조회한다. 서버가 큐 요청을 수신했을 가능성이 있는 통신 오류를 무조건 새 POST로 재시도하면 중복 생성될 수 있다. [공식 API routes](https://docs.comfy.org/development/comfyui-server/comms_routes)

runner의 기존 실행을 이어 받을 때에는 동일 workflow와 output-dir에서 `--resume`을 사용한다. 그래프·서버·출력 노드 binding이 유지되어야 하며 기록된 prompt_id의 history를 조회한다. 이미 완료된 receipt라면 로컬 출력 해시를 확인한다. resume은 새 큐 POST를 하지 않는다. `submission_unknown`은 서버 수신 여부가 불명확한 상태이므로 queue/history와 receipt를 확인하기 전 새 생성으로 덮지 않는다.

```powershell
.\.venv\Scripts\python.exe -m src.comfy_runner workspace/local/workflow_api.json --output-dir workspace/local/native_run_v1 --resume
```

runner는 서버 history의 `status.completed=true`와 출력 확인 뒤 완료 receipt를 발급한다. `receipt.json`의 `status=completed`와 `output.sha256`을 실제 `image.png`에 대조한다. 이 상태는 선택 출력의 다운로드/무결성 결과이며 작화나 작품 검수 완료가 아니다.

원본 그래프에는 작품 프롬프트, 입력 파일명, API 인증정보가 들어갈 수 있다. Git에 올릴 그래프는 검토된 범용 템플릿으로 분리하고 placeholder로 치환한다. 인증정보는 그래프나 명령 이력에 넣지 않는다.

## 5. 한 컷 실제 시험부터 시작

먼저 권한이 확인된 한 컷을 실제 생성한다. 그래프 SHA-256, prompt_id, 실제 prompt/negative prompt, 입력 파일 식별값, 모델/노드 lock, seed와 sampler 설정, 산출물 크기/해시를 묶는다. provider나 모델 내부 값을 알 수 없으면 `unknown`으로 남긴다.

생성된 원화를 직접 열어 승인된 작화 기준, 얼굴·손·소품, 카메라와 장면 목적을 확인한다. 코드 통과나 같은 seed는 동일한 그림체의 증거가 아니다. 하나의 실패가 보이면 증상 → 공통 원인 → 최소 수정 → 재발 방지 → 같은 조건의 재검증 순서로 닫는다. 조건을 바꾸지 않은 반복 생성이나 미완료 컷의 대량 확장을 하지 않는다.

한 컷이 맞으면 연결된 소수 컷에서 캐릭터·소품·시선·공간 연속성과 호흡을 확인한 뒤 회차로 확대한다. 예제/모의 출력, GPU 실행 성공, 작화 검수, 사람 승인을 각기 기록한다.

factory의 `text_only` 작업에는 검토된 text-only core graph의 완료된 runner receipt를 연결해 `provider=comfyui`로 반입할 수 있다. 허용 class는 `CheckpointLoaderSimple`, `CLIPTextEncode`, `EmptyLatentImage`, `KSampler`, `VAEDecode`, `SaveImage`, `LoraLoader`다. `LoadImage`, ControlNet, 미확인 custom node, Flux 등 별도 구조는 이 반입 경로에서 거절한다. 임의 graph를 실행하는 runner의 기능과 factory의 입력 정책은 다르다.

실제 `--prompt-file`, `--generation-record`, `--no-visual-references`가 모두 필요하다. receipt와 workflow는 job의 버전별 generation 기록에 보존되며 현재 출력 바이트와 연결된다. Comfy 출력을 imagegen로 기록하지 않는다. runner receipt만으로 factory의 `ready`, 권리 검토나 작품 승인이 부여되지는 않는다.

기존 `authorized_own_episode1_reference` 카탈로그의 허용 범위는 imagegen 경로에 결합되어 있다. 이 카탈로그만으로 ComfyUI 참조 반입을 허용하지 않는다. 별도 모델/노드/수신자 입력 계약을 검토해야 하며, factory의 현재 Comfy 반입은 `text_only`만 지원한다.

### factory 연결 순서와 공정 검토 기록

다음 예시는 사용자가 허용된 한 컷 원고와 실제 이용 근거를 준비한 뒤 실행하는 순서다. `workflow_review.json`은 선언만 채우는 통과 양식이 아니다. 실제 원고/입력/모델 이용 조건과 전송 범위를 검토한 근거 파일을 먼저 준비한다.

```powershell
.\.venv\Scripts\python.exe -m src.factory prepare workspace/local/episode_smoke.json --output-dir workspace/local/jobs/smoke_v1
.\.venv\Scripts\python.exe -m src.factory adopt-workflow workspace/local/jobs/smoke_v1 --record workspace/local/workflow_review.json
.\.venv\Scripts\python.exe -m src.factory next workspace/local/jobs/smoke_v1
```

공정 검토 record의 구조는 아래와 같다. 대문자 placeholder를 실제 확인값으로 바꾸고 evidence의 절대 경로와 SHA-256을 기록한다. 미해결 사유는 `holds`에 남긴다. 실제로 해결된 경우에만 빈 목록을 사용한다. `.env`나 `_private`의 secret 파일은 evidence로 넣지 않는다.

```json
{
  "version": "workflow-reviewed-v1",
  "legal_review_trigger": "workflow_changes_or_rights_reports",
  "reviewer": "ACTUAL_REVIEWER",
  "rights_basis": "ACTUAL_INPUT_AND_USE_BASIS",
  "license_conditions": "ACTUAL_MODEL_FONT_SOFTWARE_CONDITIONS",
  "permitted_external_processing": "ACTUAL_RECIPIENTS_AND_SCOPE",
  "review_scope": "ACTUAL_WORKFLOW_AND_LIMITS",
  "holds": ["REPLACE_WITH_ACTUAL_UNRESOLVED_ITEMS_OR_RESOLVE_THEM"],
  "evidence": [{"path": "ABSOLUTE_PATH_TO_REVIEWED_EVIDENCE.md", "sha256": "ACTUAL_64_HEX_SHA256"}]
}
```

adoption은 원고·캐릭터·컷별 브리프 해시에 결합된다. 근거나 입력이 바뀌면 재검토하며 과거 법률/Jev 미검사를 통과로 고쳐 쓰지 않는다. 공정을 채택하지 않는 작업은 `next`가 요구하는 기존 사전/최종 검토 경로를 따른다. `tools/build_layout_job.py`는 현재 검토 공정이 연결된 작업만 받는다.

`next`가 안내한 컷의 텍스트를 모델에 맞는 native graph에 넣는다. 실제 사용한 positive/negative prompt와 추가 지시는 `workspace/local/actual_prompt.txt`에 정확히 기록하고, 그래프를 API export한다. 준비 브리프를 수정했다면 수정 이력을 남기며 변경된 권한/공정 근거를 확인한다. 이후 실행과 반입은 다음과 같다.

```powershell
.\.venv\Scripts\python.exe -m src.comfy_runner workspace/local/workflow_api.json --output-dir workspace/local/native_run_v1 --check
.\.venv\Scripts\python.exe -m src.comfy_runner workspace/local/workflow_api.json --output-dir workspace/local/native_run_v1 --execute
.\.venv\Scripts\python.exe -m src.factory import workspace/local/jobs/smoke_v1 cut_001 workspace/local/native_run_v1/image.png --provider comfyui --generation-record workspace/local/native_run_v1/receipt.json --prompt-file workspace/local/actual_prompt.txt --no-visual-references
```

`text_only` 반입은 위 허용 class만 사용하는 graph로 진행한다. 다른 graph는 native runner에서 시험할 수 있지만 factory에 이식하려면 해당 노드/모델/입력의 별도 정책 검토와 구현이 필요하다. 실제 입력 선언은 그래프와 도구 실행을 정확히 반영해야 한다. 여러 컷은 컷별 새 runner 디렉터리와 receipt로 같은 과정을 반복한다.

모든 원화 반입 뒤 현재 raw 이미지·원고와 일치하는 layout 입력을 만든다. 다음 절의 한 컷 예제는 기술 시험용이며 실제 회차는 장면별 연출을 작성해야 한다.

```powershell
.\.venv\Scripts\python.exe tools/build_layout_job.py workspace/local/jobs/smoke_v1 workspace/local/layout.json --output-dir workspace/local/layout_review_v1 --font 'D:\fonts\YOUR_LICENSED_KOREAN_FONT.ttf'
.\.venv\Scripts\python.exe -m src.factory next workspace/local/jobs/smoke_v1
.\.venv\Scripts\python.exe -m src.factory review workspace/local/jobs/smoke_v1 --report workspace/local/observed_review.json
```

`observed_review.json`은 job의 현재 `review.json` 사본에 실제 검수 결과를 작성한다. 결합된 원고/원화/manifest 해시는 임의 갱신하지 않는다. 원화·식자·모바일 화면을 보지 않았다면 통과로 채우지 않는다. 제출 뒤 `next/status`로 유효성과 남은 단계를 확인한다. 기본 `factory build`는 기존 조립 경로이며 위 semantic layout 연결을 대신하지 않는다.

## 6. 원고에서 전달본까지

### 에셋 없는 한 컷 기술 입력 예시

아래를 `workspace/local/episode_smoke.json`으로 저장하면 앞 절의 `prepare` 입력으로 사용할 수 있다. 인물이나 본편 사건이 없는 기술 시험용이다. 소유자의 원고나 작화 승인으로 취급하지 않는다. `doctor`의 기본 실행은 text-only 환경을 확인하며 참조 카탈로그를 요구하지 않는다.

```json
{
  "title": "한 컷 파이프라인 기술 시험",
  "generation_input_mode": "text_only",
  "cuts": [{
    "id": "cut_001", "page": 1,
    "description": "사람과 글자가 없는 중립적인 빈 작업대.",
    "prompt": "A neutral empty tabletop, no people, no text, no logos.",
    "characters": [],
    "dialogue": [{
      "text": "식자 시험", "type": "normal", "style": "editorial",
      "font_size": 32, "balloon_variant": "B",
      "box": [0.05, 0.02, 0.4, 0.15]
    }]
  }]
}
```

이 예제의 `box`는 임시 배치 입력이며 다음 `measured_bands` 단계에서 폰트와 B/C의 실측 몸체로 다시 계산한다. 직접 장면에 겹쳐 놓는 식자는 실측 너비/높이에 맞는 box를 작성해야 하며 임의 box 크기를 그대로 쓰면 오류가 난다.

원화 한 컷을 실제 반입한 뒤 아래 Python을 `workspace/local/make_smoke_layout.py`로 저장하고 저장소 루트에서 실행한다. 이 helper는 반입된 실제 이미지 크기와 정규화된 원고/대사를 읽는다. 기술 시험 한 컷에만 적용하는 `wide/present/ending` 설정이며 본편 전체의 자동 배치 규칙이 아니다.

```python
import json
from pathlib import Path
from PIL import Image

root = Path("workspace/local/jobs/smoke_v1").resolve()
job = json.loads((root / "job.json").read_text(encoding="utf-8"))
episode = json.loads((root / job["episode"]).read_text(encoding="utf-8"))
assert len(job["cuts"]) == len(episode["cuts"]) == 1
cut, record = episode["cuts"][0], job["cuts"][0]
raw = root / record["imported"]["image"]
with Image.open(raw) as image:
    width, height = image.size
art_height = round(height * 800 / width)
panel = {
    "id": cut["id"], "role": "wide", "time_layer": "present",
    "link_after": "ending", "source_image": raw.as_posix(),
    "source_width": width, "source_height": height,
    "description": cut["description"], "dialogue": cut["dialogue"],
    "lettering_mode": "measured_bands",
    "old_geometry": {"x": 0, "top": 0, "art_width": 800,
                     "art_height": art_height, "canvas_height": art_height}
}
layout = {"title": episode["title"], "expected_ids": [cut["id"]], "panels": [panel]}
Path("workspace/local/layout.json").write_text(
    json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
```

```powershell
.\.venv\Scripts\python.exe workspace/local/make_smoke_layout.py
```

이 입력으로 앞 절의 `build_layout_job`을 실행하고 원화·말풍선·모바일 화면을 직접 본다. B/C 타입을 바꾸어 볼 때도 기존 후보를 보존하고 새 검토본으로 만든다. 기술 시험의 헤더 띠 배치를 실제 회차의 고정 양식으로 복사하지 않는다.

### 실제 회차 공정

1. **계획**: 원고 장면 ID·순서, 인물/소품 상태, 시점, 보여 줄 정보와 연출 의도, 검수 질문을 고정한다.
2. **간단한 구도**: 인물 위치·시선·동선·핵심 소품·컷 크기와 대사 공간을 선 도식이나 텍스트로 정리한다. 상세 AI 밑그림의 반복 생성은 필수 단계가 아니다. 구도를 텍스트 지시로 전달하고, 도식 이미지를 생성 입력에 추가하려면 별도 허용 범위를 확인한다.
3. **원화**: 승인된 입력만 사용해 ComfyUI에서 생성하고 실제 prompt/graph/모델/입력/출력 기록을 남긴다. 원고의 사건을 구도 편의를 위해 바꾸지 않는다. 원화에는 대사를 생성하지 않고 식자를 분리한다.
4. **B/C 식자와 장면 배치**: `src.balloon_sizing`, `src.editorial_lettering`, `src.layout_lettering`과 `src.layout_policy`의 계약을 사용한다. B/C를 명시하고 실제 폰트 실측을 유지한다. 과거 회차의 좌표나 타입을 그대로 복사하지 않는다.
5. **실제 검수와 수정**: 원화, 식자 컷, 세로 조립본, 모바일 정지 화면을 직접 확인한다. 구도·연기·연속성·호흡·조명·식자·원고 충실도의 7항목에 관찰 근거를 남긴다. 보지 않은 항목은 `not_reviewed`다.
6. **고지·식별·증빙**: 실제 AI 활용과 권리 검토 범위에 맞는 고지를 전달본 상단에 둔다. 최종 파일 해시와 제작/수정/검수 이력을 연결한다. 식별 워터마크는 출처 확인을 보조하며 복제·AI 입력을 기술적으로 차단하거나 권리를 인증하지 않는다.
7. **기록 적재와 전달**: 아래 보관 기준에 따라 원본과 이력을 적재하고 읽기 검증을 마친다. 기술 완료와 최종 작품/공개 승인을 분리한다.

말풍선은 장면 위에 놓을 수 있다. 실제 빈 공간에 `art_anchor`를 지정하고 `protected_art_boxes`로 얼굴·손·핵심 행동/단서를 보호한다. 공간이 부족하면 배치·컷 여백을 조정한다. 모든 대사를 바깥 띠로 밀거나 읽기 크기를 줄이는 것을 자동 해결책으로 삼지 않는다. 기하 충돌 검사는 시각 검수를 대체하지 않는다.

배치 입력과 폰트가 준비된 뒤의 호출 예시는 다음과 같다. 입력/출력은 프로젝트 안의 별도 경로를 사용하고 기존 검토본을 보존한다.

```powershell
.\.venv\Scripts\python.exe tools/apply_layout_policy.py workspace/local/layout.json --output-dir workspace/local/layout_review_v1 --font 'D:\fonts\YOUR_LICENSED_KOREAN_FONT.ttf'
```

고지 패키지는 `tools/package_webtoon.py --help`의 입력 계약을 따라 실제 고지 JSON을 명시해 새 전달본으로 만든다. 비공개 제작 폴더의 기본 설정이 clean checkout에도 있다고 가정하지 않는다. 존재하지 않는 제보 채널을 운영 중으로 표시하지 않는다.

RGB PNG 전달 사본의 식별 표식은 `tools/mark_review.py`로 넣고 확인할 수 있다. 아래 경로와 owner/work label은 형식 예시다. 처음에는 `init-key`로 32바이트 비공개 키를 만들고, 다음 실행부터 같은 키를 별도 보관해 사용한다. 기존 키는 덮어쓰지 않으며 키 파일을 Git이나 제작 기록에 올리지 않는다.

```powershell
.\.venv\Scripts\python.exe tools/mark_review.py init-key workspace/_private/mark.key
.\.venv\Scripts\python.exe tools/mark_review.py embed workspace/local/delivery.png workspace/local/delivery_marked.png --owner OWNER_LABEL --work-id WORK_ID --key-file workspace/_private/mark.key
.\.venv\Scripts\python.exe tools/mark_review.py verify workspace/local/delivery_marked.png --key-file workspace/_private/mark.key
```

기존 파일은 덮어쓰지 않는다. `embed` 결과의 output SHA-256과 asset ID를 비공개 장부에 보관하고 이후 `verify --sha256 ... --asset-id ...`로 해당 파일을 대조할 수 있다. 고지 영역을 보존하려면 실제 높이를 측정해 `--protected-top`을 지정한다. 표식은 픽셀을 바꾸므로 최종 manifest와 해시를 다시 만들고 해당 전달본을 직접 검수한다. 이 도구는 원본 PNG metadata를 복사하지 않으며 provider 고지·서명된 C2PA·권리 증빙을 대신하지 않는다.

## 7. 비공개 보관과 재개

- Git: 검토된 재사용 소스, 범용 템플릿, 사용법과 source-only 검사만 보관한다. private repository도 작품 에셋·secret을 넣는 근거가 되지 않는다.
- Google Drive 비공개 제작 전용 폴더: 허용된 모든 단계의 이미지·텍스트·거절/수정본·실제 검수·결정·최종 결과, 전체 원본 바이트와 실행/전달 증빙을 한 폴더 아래 연결한다. 요약이나 연락시트만으로 전체 기록을 대체하지 않는다. 저장 대상은 소유자가 지정한 폴더를 사용하며 공유 권한을 확대하지 않는다. Figma 병행 기록은 필수가 아니며 과거 기록은 보존한다.
- 로컬: 작업 중 자료는 검증이 끝날 때까지 임시 보유한다. 최종적으로 릴리즈 가능한 전달본을 남기되, 적재·재개 정보·실제 원본 readback 검증이 끝나기 전 원본을 삭제하지 않는다.

적재 장부에는 로컬 원본 SHA-256, Drive file/folder ID와 URL, 원본과 전송본의 해시/변환 관계, 바이트 수, 업로드 시각, readback 결과, 미반입 이유를 기록한다. 폴더 목록에 보인다는 사실이나 로컬 Drive 동기화 표시를 원격 원본 바이트 검증으로 바꾸어 적지 않는다.

인증정보, 개인 대화 캡처, 허락 없는 원문은 자동 적재하지 않는다. 다음 에이전트를 위한 재개 기록에는 현재 단계, 유효한 입력/그래프/산출물 해시, 열린 결함, 실제 승인 범위, 다음 한 단계, 복구 명령을 남긴다. 개인 파일 경로·서명 URL·키를 공개 인계 문서에 쓰지 않는다.

## 8. 검증 보고의 최소 범위

완료 보고에는 실행한 commit와 검사 범위, 실패/보류 항목을 함께 적는다.

- offline tests와 dry-run: 설치/입력/계산/프로토콜의 확인이다.
- GET preflight: 해당 서버의 노드와 모델 목록 확인이다.
- 실제 한 컷: 해당 모델·그래프·장치에서 결과 이미지가 생성됐다는 증거다.
- 실제 원화/식자/모바일 검수: 관찰한 해당 버전의 품질 근거다.
- 적재 readback: 해당 바이트가 지정 저장소에서 다시 읽혔다는 증거다.
- 사람 승인: 명시적으로 받은 범위만 기록한다.

미실행 GPU 시험, 모델/참조 미확보, 미해결 권리 문제를 테스트 성공으로 덮지 않는다. 법률 API/Jev는 허용된 최소 사실로 공정 변경이나 구체적 권리 의심을 검토하는 보조 수단이다. 코드가 요구하는 현재 작업의 게이트를 따르되 모델 확률이나 운영자 선언을 무침해 보증으로 표시하지 않는다. 자세한 범위는 [권리 안전 절차](COPYRIGHT_SAFETY.md)와 [법률 QA](LEGAL_QA.md)를 따른다.
