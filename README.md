# toon_lab

원고와 컷 이미지를 세로 스크롤 웹툰으로 조립하는 로컬 제작 도구입니다. 이미지 생성 도구를 가진 AI 에이전트는 클론한 폴더에서 원고 정리부터 컷 생성, 한글 식자, 세로 PNG 조립까지 진행할 수 있습니다.

## 첫 웹툰 만들기

**준비물**은 Git, Python 3.11 이상, 이미지 생성·보기와 로컬 파일 저장·명령 실행이 가능한 AI 에이전트입니다.

### 1. 저장소 받기

```sh
git clone https://github.com/DoHyunBak/toon-lab.git
cd toon-lab
```

### 2. AI 에이전트에서 폴더 열기

방금 받은 `toon-lab` 폴더를 에이전트의 작업 폴더로 열고 아래 요청을 복사해 보세요.

```text
이 폴더의 AGENTS.md를 읽고, 네 이미지 생성 도구로 샘플 웹툰 한 컷을 만들어줘.
그림에 글자를 그리지 말고 나중에 한글로 식자해줘. 완성 PNG 경로도 알려줘.
```

내 이야기로 만들려면 원고를 채팅에 붙이거나 파일 경로를 알려주세요. 아이디어로 시작할 때는 아래 예시처럼 소재와 컷 수를 적으면 됩니다.

```text
비 오는 날, 길고양이가 우산 아래로 들어오는 짧은 이야기를 4컷 세로 웹툰으로 만들어줘.
먼저 한 컷으로 그림체를 확인한 다음, 나머지 컷을 만들고 한글 대사를 넣어줘.
```

에이전트가 Python 환경과 Pretendard를 준비하고, 원화에 한글 말풍선을 올려 조립합니다. 이미 연결된 이미지 도구를 쓰는 경우 추가 API 키와 ComfyUI 설치는 필요 없습니다.

### 3. 결과 열기

작업과 결과는 `workspace/local/` 아래에 저장됩니다. 에이전트가 알려주는 작업 폴더에서 다음 파일을 여세요.

- **`full_strip.png`** — 한 화 전체를 담은 세로 이미지
- **`slice_001.png` 등** — 나누어 저장한 세로 이미지
- **`read.html`** — 고지 포함 검토본을 만든 경우 브라우저에서 여는 미리보기

이미지 생성 도구가 없는 경우 아래 오프라인 데모로 식자와 조립을 시험할 수 있습니다. 세부 명령은 [에이전트 이미지 제작 절차](docs/public/AGENT_IMAGE_WORKFLOW.md)에 있습니다.

## 명령줄에서 오프라인 데모 실행

Windows PowerShell에서는 클론한 폴더에서 실행합니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tools/setup_open_fonts.py
.\.venv\Scripts\python.exe -m src.demo
```

macOS와 Linux에서는 다음 명령을 실행합니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/setup_open_fonts.py
.venv/bin/python -m src.demo
```

폰트 설치 도구는 공식 Pretendard 파일과 OFL 고지를 내려받아 해시를 확인합니다. 데모가 끝나면 `workspace/06_output_webtoon/demo/full_strip.png`를 여세요. 데모는 예제 원고와 합성 컷을 사용합니다.

Python이나 폰트가 인식되지 않으면 가상 환경의 Python으로 `-m src.factory doctor`를 실행해 어느 단계가 빠졌는지 확인하세요. [폰트 설치 안내](docs/public/FONTS.md)와 [문제 해결](docs/public/TROUBLESHOOTING.md)도 볼 수 있습니다.

## 제작 흐름

1. 원고를 장면별 텍스트 브리프로 정리하고 사용할 이미지와 입력 권한을 확인합니다.
2. 원화를 준비해 등록하고 말풍선, 효과음, 컷 사이 여백을 조정합니다.
3. 세로 PNG를 조립하고 모바일 폭에서 흐름과 가독성을 확인합니다.

[제작 절차](docs/public/PRODUCTION_RUNBOOK.md)와 [식자·편집 가이드](docs/public/EDITORIAL_LETTERING_PLAYBOOK.md)에 작업별 명령과 예제가 있습니다. 로컬 GPU 제작을 선택한 경우 [ComfyUI 설치·실행 안내](docs/public/COMFYUI_HANDOFF.md)를 따르세요.

## 공개 범위

공개본에는 제작 코드, 문서, 테스트, 범용 JSON 예제가 들어갑니다. 원고, 컷 이미지, 제작 기록, 모델 가중치, 폰트 파일, 인증정보는 각자의 로컬 작업 공간에서 관리합니다. 이 도구는 운영자가 관리하는 로컬 환경에서 사용하세요. 파일 처리 기능과 ComfyUI API를 인터넷에 직접 노출하면 외부 사용자가 접근할 수 있습니다.

- [소스 공개 절차](docs/public/RELEASING.md)
- [보안 정책과 취약점 제보](SECURITY.md)
- [MIT 라이선스](LICENSE)와 [제3자 고지](THIRD_PARTY_NOTICES.md)
- [라이선스 적용 범위](docs/public/LICENSE_SCOPE.md)
