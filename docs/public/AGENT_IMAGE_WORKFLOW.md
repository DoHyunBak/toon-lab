# 이미지 생성 에이전트로 첫 웹툰 만들기

클론한 폴더에서 이미지 생성·보기·로컬 파일 저장·명령 실행이 가능한 에이전트를
연다. “샘플 웹툰 한 컷 만들어줘” 또는 “이 원고를 네 이미지 도구로 4컷 웹툰으로
만들어줘”라고 요청하면 아래 순서로 실행한다. 원고 파일은 TXT, JSON 또는 채팅의
글을 받아 작업용 JSON으로 정리할 수 있다.

## 1. 로컬 환경과 원고

- 사용 가능한 이미지 생성 도구와 파일 접근 방식을 확인한다. 이미 연결된 도구를
  사용한다. 이미지 보기만 가능하거나 생성본을 로컬 파일로 받을 수 없다면 해당
  제약을 알리고, 원고 정리나 오프라인 데모까지 진행한다.
- [설치 명령](../../README.md)을 참고해 Python 3.11 이상과 프로젝트 가상 환경을
  확인한다. 필요한 경우 저장소 안에 `.venv`를 만들고 의존성과 Pretendard를
  설치한다. 이후 명령의 `python`은 해당 가상 환경의 실행 파일이다. 활성화
  없이 Windows에서는 `.venv/Scripts/python.exe`, Linux와 macOS에서는
  `.venv/bin/python`을 직접 호출할 수 있다. `python -m src.factory doctor`로
  로컬 조립 환경을 확인한다. 명령 출력을 읽는 에이전트는 아래처럼 `-X utf8`로
  한글 JSON의 인코딩을 고정한다.
- 새 작업마다 `workspace/local/` 아래 고유한 폴더를 사용한다. 기존 작업을 이어
  달라는 경우에는 `status`와 `next`를 먼저 읽는다. 출력이 이미 있으면 덮어쓰지
  않는다. 비공개 입력과 출력은 Git의 무시 경로에 둔다.
- 실제 원고는 사건, 컷 순서와 대사를 유지한다. 아이디어부터 창작을 요청받았으면
  짧은 콘티를 만들고 [스토리 검토](AUTHORING_WORKFLOW.md)를 거친다. 컷 수를
  위임받았으면 첫 시도는 3~5컷이 적당하다. 등장인물은 고정된 외형과 의상 설명을
  `characters.json`에 두고 각 컷의 `characters`에 해당 ID를 쓴다.

샘플을 요청받으면 다음 범용 예제를 `workspace/local/first-comic/episode.json`에
저장한다. 실제 원고를 사용할 때는 내용을 교체한다.

```json
{
  "title": "비 오는 오후",
  "generation_input_mode": "text_only",
  "cuts": [
    {
      "id": "cut_001",
      "description": "비 오는 카페. 작은 테이블에 접힌 파란 우산과 흰 머그잔이 놓여 있다.",
      "prompt": "부드러운 색감과 또렷한 선. 화면 윗부분은 비워 둔다.",
      "dialogue": [
        {"text": "비가 그칠 때까지.", "type": "narration", "position": "top"}
      ]
    }
  ]
}
```

```sh
python -m src.factory prepare workspace/local/first-comic/episode.json --output-dir workspace/local/first-comic/job
```

등장인물 ID가 있는 원고에는 `--characters`와 등록 파일 경로를 추가한다. 등록
파일은 `{"characters":{"mina":{"description":"짧은 검정 단발, 초록 재킷"}}}`처럼
작성한다.

## 2. 실제 입력 범위를 확인하고 한 컷 생성

원고와 프롬프트의 사용 근거, 현재 이미지 도구의 이용 조건, 해당 도구에 보낼 수
있는 텍스트의 범위를 확인한다. 외부 도구라면 전송이 허용된 장면 정보만 넣고
실제 원고 파일과 이미지 참조, 인증정보는 첨부하지 않는다. 미해결 조건이 있으면
해당 생성은 보류한다.

확인한 사실과 근거 문서의 경로·SHA-256으로 `workspace/local/first-comic/workflow.json`을
작성한다. 근거 문서는 작업 폴더의 TXT, Markdown 또는 JSON으로 남긴다. 아래
각 항목은 현재 자료를 확인한 내용으로 채우고, SHA-256은 실제 파일 바이트를
계산한다. `holds`는 미해결 조건이 없을 때 빈 배열을 사용한다.

```json
{
  "version": "workflow-reviewed-v1",
  "legal_review_trigger": "workflow_changes_or_rights_reports",
  "reviewer": "<ACTUAL_REVIEWER>",
  "rights_basis": "<MANUSCRIPT_AND_INPUT_RIGHTS>",
  "license_conditions": "<ACTUAL_TOOL_AND_FONT_CONDITIONS>",
  "permitted_external_processing": "<ACTUAL_TOOL_AND_ALLOWED_TEXT_SCOPE>",
  "review_scope": "<EPISODE_AND_ALLOWED_ACTIONS>",
  "holds": [],
  "evidence": [{"path": "<ABSOLUTE_EVIDENCE_FILE>", "sha256": "<ACTUAL_SHA256>"}]
}
```

```sh
python -m src.factory adopt-workflow workspace/local/first-comic/job --record workspace/local/first-comic/workflow.json
python -X utf8 -m src.factory next workspace/local/first-comic/job
```

`generate`가 반환되면 `imagegen.prompt`를 에이전트의 이미지 생성 도구에
텍스트로 전달한다. 생성할 컷마다 장면·카메라·소품·대사 공간을 명시하고 고정
인물 설명을 유지한다. 그림에 대사를 그리게 하지 않는다. 사용한 도구와 모델,
실제로 전달한 프롬프트와 생성 파일을 로컬에 보존한다. 모델명이 제공되지
않았다면 도구 이름과 함께 미공개라고 기록한다. 프롬프트를 도구 형식에 맞게
조정했다면 조정한 실제 텍스트를 저장한다.

첫 결과에서 행동과 구도, 글자가 생기지 않았는지, 대사 공간이 남았는지를 직접
본다. 이어지는 컷에서는 인물·의상·소품 위치를 나란히 비교한다. 이전 이미지는
검수에만 쓰고, 대화 이미지가 자동으로 포함되는 도구라면 텍스트 전용 요청을
사용한다. 현재 도구에서 이를 제어할 수 없으면 해당 생성을 보류한다.

```sh
python -m src.factory import workspace/local/first-comic/job cut_001 workspace/local/first-comic/cut_001.png --provider imagegen --prompt-file workspace/local/first-comic/cut_001.prompt.txt --no-visual-references
python -X utf8 -m src.factory next workspace/local/first-comic/job
```

`imagegen`은 에이전트가 생성한 이미지를 반입하는 CLI 분류다. 실제 도구와 모델
이름은 작업 기록에 남긴다. 원화 등록 후 `next`를 반복해 빠진 컷만 제작한다.
중단 후 재개할 때 등록 대기 중인 원화와 프롬프트가 있으면 먼저 그 파일을 검수한다.
교체가 필요하면 새 생성본과 실제 프롬프트를 준비하고 `import --replace`로
이전을 보존한다. `next`가 입력 변경이나 보류를 보고하면 원인을 해결한 뒤 이어간다.

## 3. 식자, 조립, 전달

```sh
python -m src.factory build workspace/local/first-comic/job
python -X utf8 -m src.factory next workspace/local/first-comic/job
```

기본 조립은 한글 식자 후 `job/output/full_strip.png`와 `slice_*.png`를 만든다.
장면별 폭이나 B/C 실측 말풍선이 필요하면
[식자·편집 기준](EDITORIAL_LETTERING_PLAYBOOK.md)과 [제작 절차](PRODUCTION_RUNBOOK.md)의
레이아웃 경로를 사용한다. 조립본을 실제 이미지로 보고 모바일 폭에서 읽기 순서,
대사·꼬리, 잘림, 장면 호흡을 확인한다. `next`가 준 검수 양식의 복사본에 실제
관찰만 기록한 뒤 `python -m src.factory review JOB --report FILE`로 제출한다.

고지 포함 내부 검토본은 다음 명령으로 만든다. 검토 폴더의 `read.html`을 열면
분할 PNG를 세로로 이어 볼 수 있다. 실제 제보 창구가 없다면 내부 검토 상태로 둔다.

```sh
python tools/package_webtoon.py workspace/local/first-comic/job/output/manifest.json --output-dir workspace/local/first-comic/review-v1
```

[고지·증빙 절차](PRODUCTION_RUNBOOK.md)를 적용하고 필요하면
[PNG 무손실 압축](PNG_COMPRESSION.md)으로 새 경로에 저장한다. PNG, 분할본,
원고와 작업 기록 경로를 알려준다. 확인하지 못한 검수 항목은 미확인으로 남긴다.
기본 전달은 로컬 파일이며 게시와 외부 백업은 별도 요청이 있을 때 진행한다.
