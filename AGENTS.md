# toon_lab 에이전트 작업 지침

신규 대사·효과음·제목·고지는 검토된 오픈 라이선스 폰트만 사용한다. 기본은
Pretendard Medium(500), 명시적 강조는 Bold(700)이며 업계 통계가 아닌 제작 기준이다.
준비는 `python tools/setup_open_fonts.py`, 실제 파일·OFL 검사는 `src/font_policy.py`를
따른다. 시스템 폰트 fallback을 쓰지 않고, 전달 ZIP에 `font_licenses.json`과
`licenses/Pretendard-OFL.txt`를 포함한다. 기존 완성본·과거 기록은 변경하지 않는다.

현재 사용자가 지정한 작업 범위와 실제 실행 환경을 우선한다.

## 웹툰 제작 요청

“웹툰 만들어줘”, “샘플 웹툰 한 컷”, “이 원고를 웹툰으로”처럼 제작을 요청하면
[에이전트 이미지 제작 절차](docs/public/AGENT_IMAGE_WORKFLOW.md)를 먼저 따른다.
현재 에이전트가 사용할 수 있는 이미지 생성 도구와 로컬 저장 가능 여부를 확인하고
기존 도구로 한 컷부터 진행한다. 스킬 등록은 필수가 아니다. 일반 제작 요청에
ComfyUI 설치, 별도 계정 또는 추가 API 키를 요구하지 않는다.

원고가 있으면 사건과 대사를 보존한다. 아이디어를 주며 창작을 요청하면 짧은 초안을
작성하고, 샘플을 요청하면 안내서의 범용 예제를 쓴다. 원하는 이야기나 자료가 전혀
없으면 핵심 설정 한 가지를 확인하는 동안 로컬 환경을 준비한다.

“착수해”, “시작해”는 대화의 현재 목표를 이어간다. 목표가 아직 없으면 웹툰 제작
환경을 확인한다. “Comfy 착수”처럼 사용자가 로컬 GPU 경로를 선택했으면
[ComfyUI 착수 지시](docs/public/START_PROMPT.md)를 읽고 진행한다.

스킬이 등록되지 않아도 `docs/public/skills/toon-comfy-start/SKILL.md`를 직접 읽어
실행할 수 있다. 기존 정상 환경과 같은 목표의 실제 실행 상태를 확인해 재사용·재개하고,
이미 유효하게 완료된 한 컷을 중복 생성하지 않는다. 완료 증거는 현재 graph·출력·환경에
결합돼야 하며 모의 테스트 기록을 대신 쓰지 않는다.

이 규칙은 사용자의 실제 착수 요청에 적용한다. “착수 프롬프트 수정” 같은 문서 작업이나
인용문 속 단어를 설치·GPU 생성 명령으로 해석하지 않는다.

먼저 [시작 규칙](docs/public/AGENT_START.md), [인계 범위](docs/public/HANDOFF_COVERAGE.md),
[공정 결정](docs/public/WORKFLOW_DECISIONS.md)을 읽는다. 오류가 있으면
[트러블슈팅](docs/public/TROUBLESHOOTING.md)을 증상으로 찾는다.

## 작업에 맞는 스킬

- 설치부터 로컬 한 컷 시험: `docs/public/skills/toon-comfy-start/SKILL.md`
- 허용된 원고의 실제 회차 제작·검수: `docs/public/skills/toon-production/SKILL.md`
- 중단·실패·컨텍스트 인계에서 재개: `docs/public/skills/toon-recover/SKILL.md`

해당 파일을 직접 읽으면 설치 없이도 절차를 사용할 수 있다. Codex의 프로젝트
스킬로 등록하려면 `python tools/install_workflow_skills.py --check`로 먼저 확인한 뒤
`python tools/install_workflow_skills.py --install`을 실행한다. 설치기는 이 저장소의
세 스킬만 `.agents/skills/`에 복사하고 다른 기존 지침이나 사용자 전역 설정은
덮어쓰지 않는다. 새 스킬 검색을 지원하는 클라이언트에서는 새 대화/새로고침 뒤
`$toon-comfy-start`, `$toon-production`, `$toon-recover`를 사용한다.

## 지켜야 할 경계

1. 확인한 실수를 다음 실제 입력·코드·검사에 반영한다. 기록만 남기고 같은 실패를 반복하지 않는다.
2. 계획과 실제 실행을 구분한다. mock, CUDA 연산, GPU 이미지 생성, 시각 검수와 사람 승인을 각각 기록한다.
3. 원고 사건·ID·순서를 보존한다. 상세 AI 러프 반복 대신 간단한 선/텍스트 구도를 사용한다.
4. 현재 ComfyUI factory 반입은 검토된 core text-only 그래프에 한정된다. 기존 imagegen 참조 허용을 ComfyUI 허용으로 바꾸지 않는다.
5. B/C 실측 글자 크기를 유지하고 장면 위 빈 공간과 보호 영역을 직접 지정한다. 식자와 모바일 결과를 실제로 본다.
6. 새 후보·수정은 이전 바이트·검수·거절 이력을 보존한다. receipt나 상태를 편집해 완료·승인으로 만들지 않는다.
7. Git에는 검토된 소스·운영 지식만 넣는다. 원고·실제 프롬프트·모델·폰트·이미지·개인 기록·secret은 제외한다.
8. 기본 전달 위치는 로컬이다. 원본과 작업 기록을 보존한다. 비공개 외부 적재는 사용자가 별도로 지정한 범위에서 수행하고 원본 바이트를 검증한다.

커밋·push·외부 전송·유료 사용은 현재 사용자 지시가 허용한 범위에서만 실행한다.
불필요하게 같은 승인을 반복해서 묻지 않는다. 필요한 실제 입력이나 권한이 없으면
해당 부분을 분리해 설명하고, 독립적으로 할 수 있는 작업을 계속한다.
