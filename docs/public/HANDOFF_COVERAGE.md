# 에셋 없는 제작 인계의 포함 범위

생성형 AI 이미지 도구와 Python을 사용하는 공정 지도다. 이전 작업의 재사용 가능한 코드와 방법을 어디서
이어받는지, 사람이 수행해야 하는 단계와 아직 지원하지 않는 부분을 구분한다.
기존 작품이나 비공개 제작 기록을 복제한 목록은 제공하지 않는다.

**코드 전달과 제작 완료는 서로 다른 상태다.** 공개 소스는 명시적 공개 목록으로 관리한다. 실제 릴리즈 파일 목록과 바이트는
[public-release.json](../../public-release.json)과 새 export의
`RELEASE_MANIFEST.json`으로 확인한다. 이 문서나 파일 수만으로 AI 원화 생성, 작품
품질, 외부 적재 또는 권리 검토가 끝났다고 판단하지 않는다.

## 읽는 순서와 스킬

처음 받은 에이전트는 [저장소 시작 규칙](../../AGENTS.md),
[시작 지침](AGENT_START.md), [복사해서 사용할 착수 요청](START_PROMPT.md)을 읽는다.
실제 명령은 [에이전트 이미지 제작 절차](AGENT_IMAGE_WORKFLOW.md),
[제작 운영 절차](PRODUCTION_RUNBOOK.md),
[세션 상태와 재개](SESSION_CONTINUITY.md)를 따른다.

공개 스킬의 원본은 다음 문서다. 스킬을 설치했다는 사실은 모델, 서비스 계정,
작품 입력, 생성·전송 권한이나 이미지 도구 연결가 완료됐다는 뜻이 아니다.

- [toon-production](skills/toon-production/SKILL.md): 원고에서 검토본·증빙까지 제작.
- [toon-recover](skills/toon-recover/SKILL.md): 실패·중단·컨텍스트 변경 뒤 안전한 재개.

과거 로컬 스킬과 연구 도구의 폴더 전체를 이 스킬로 간주하지 않는다. 현행 공개
계약에 맞춰 작성된 위 문서와 실제 체크아웃의 CLI를 사용한다.

## 1. 로컬 조립 환경과 이미지 도구

**전달됨:** [runtime_check.py](../../src/runtime_check.py)는 Python·Pillow·한글 폰트와
PNG 저장 상태를 확인한다. 실제 원화는 에이전트에 연결된 이미지 생성 도구로 만든다.
[에이전트 이미지 제작 절차](AGENT_IMAGE_WORKFLOW.md)에 준비·생성·반입 순서가 있다.
[demo.py](../../src/demo.py)는 식자·조립을 시험할 오프라인 도식을 만들며 실제 AI
원화나 승인된 본편을 만들지 않는다.

**운영자가 확인:** 이미지 도구의 생성·파일 저장 가능 여부, 입력 자료의 이용 권한,
Python·Pillow·폰트의 준비 상태, 실제 한 컷 생성과 작화 비교.
[환경 양식](templates/environment.lock.example.json)의 빈 값은 확인 완료가 아니다.

**포함하지 않음:** 이미지 생성 모델·런타임, 서비스 계정, 폰트 바이너리, 입력 이미지.
오프라인 검사는 실제 AI 원화 생성과 시각 검수를 대신하지 않는다.

## 2. 원고, 입력 허용 범위와 검토 공정

**전달됨:** [script_formatter.py](../../src/script_formatter.py),
[factory.py](../../src/factory.py), [generation_policy.py](../../src/generation_policy.py),
[owned_episode_reference.py](../../src/owned_episode_reference.py),
[workflow_policy.py](../../src/workflow_policy.py)는 입력 계약, 준비, 원고 결합과
별도 검토된 공정의 상태를 다룬다. [운영 절차](PRODUCTION_RUNBOOK.md)와
[권리 안전 절차](COPYRIGHT_SAFETY.md)가 운영자의 확인 범위를 설명한다.

**운영자가 수행:** 실제 원고·캐릭터 설정을 제공하고 허용된 행위·목적·수신자와
근거를 확인한다. `text_only`에는 자체 이미지도 넣지 않는다. 이전 서비스에서
허용된 자체 이미지 참조를 새 모델·서비스에 자동 확대하지 않는다. 실제 사용한
도구와 입력 범위를 사실대로 기록하며 provider나 mode를 바꿔 등록하지 않는다.

**의도적으로 제외:** 작품별 원고·대사·설정·권한 장부·실제 참조 카탈로그,
과거 승인 메시지와 채운 검토 기록. 다른 소유자의 작품을 재개하려면 허용된
비공개 전달을 별도로 받아야 한다.

## 3. 작가 역량, 장면 의도와 간단한 구도

**방법 전달됨:** [작가·연출 작업법](AUTHORING_WORKFLOW.md)은 구상, 선택과 인과,
정보 공개, 대사, 연기, 배경, 연속성, 식자와 모바일 검수의 질문을 정리한다.
현재의 제한된 연구 관점 13개를 빠짐없이 재인덱스하고, 추가 편집 가설과 구분한다.
출처 URL·확인 범위·한계를 남기며 원문이나 타 작품 사례를 싣지 않는다.

**부분 자동화:** [production_control.py](../../src/production_control.py)와
[compile_production_batch.py](../../tools/compile_production_batch.py)는 원고 해시,
장면 ID·순서·원문 사건과 현재 상태를 결합한다. 실제 입력에 어떻게 연결하는지는
[운영 절차](PRODUCTION_RUNBOOK.md)에 있다.

**수동 또는 미지원:** 원고의 의미를 자동으로 이해해 구도·표정·소품 상태를
결정하지 않는다. 모든 신규 생성에 선 구도 계획을 강제로 요구하는 독립 CLI는
공개 공정에 구현되어 있지 않다. [구도 계획의 사전 확인](AUTHORING_WORKFLOW.md#구도-계획의-사전-확인)은
운영자가 수행한다. 간단한 선 도식을 상세 AI 밑그림 반복 생성으로 바꾸지 않는다.

## 4. 실제 생성 기록, 반입과 실패 복구

**전달됨:** [factory.py](../../src/factory.py), [operations.py](../../src/operations.py)는 생성 기록,
실제 산출물 반입, 원본·이전 버전 보존, 현재 증빙 확인과 다음 단계를 다룬다.
[production_control.py](../../src/production_control.py)는 수정 지시 정리와
기록된 재계획 상태의 해시 결합을 지원한다.

**운영자가 수행:** 실제 도구·프롬프트와 현재 장면의 일치 여부 확인, 거절 사유와
안정적인 실패 분류 기록, 수정 방법 변경, 작은 재시험과 관찰.
[운영 절차](PRODUCTION_RUNBOOK.md)와 [복구 스킬](skills/toon-recover/SKILL.md)을 사용한다.
반복 실패 판단 함수가 있다고 해서 모든 외부 생성 경로가 거절 기록을 자동으로
작성하거나 모든 재시도를 차단하는 것은 아니다.

**한계:** 로컬 receipt와 해시는 파일 결합 근거다. 제공자가 서명한 증명, 입력
권한, 원고 충실도나 실제 그림체 일치의 자동 판정은 아니다. 요청 결과를 모르는
상태에서 새 작업을 무조건 제출하는 복구는 지원하지 않는다.

## 5. B/C 식자, 장면 중첩과 세로 배치

**전달됨:** [balloon_sizing.py](../../src/balloon_sizing.py),
[editorial_lettering.py](../../src/editorial_lettering.py),
[bubble_renderer.py](../../src/bubble_renderer.py),
[layout_lettering.py](../../src/layout_lettering.py)는 글자 실측과 식자를 다룬다.
[layout_policy.py](../../src/layout_policy.py), [layout_composer.py](../../src/layout_composer.py),
[webtoon_stitcher.py](../../src/webtoon_stitcher.py),
[apply_layout_policy.py](../../tools/apply_layout_policy.py),
[build_layout_job.py](../../tools/build_layout_job.py)는 편집 주석에 따른 배치·조립과
factory 검수 결합을 지원한다.

**운영자가 수행:** B/C 선택, 화자와 대사 순서, 원화의 실제 빈 공간, 얼굴·손·단서
보호 영역, 역할·시간·전환 의도를 작성한다. job 검수와 결합해야 하는 결과는
`build_layout_job.py`의 계약을 따른다. 독립 렌더 결과만 만들고 factory가 그
출력을 현재 검토본으로 알고 있다고 가정하지 않는다.

**한계:** 얼굴·행동의 의미 인식, 자동 미감 점수, 인물을 가리지 않는 위치의
자동 발견은 구현되어 있지 않다. 테스트의 synthetic 텍스트·폰트 탐색은 실제
작품 식자 승인이나 모든 플랫폼의 표시 검증이 아니다.

## 6. 실제 관찰 검수와 의미 판단 보조

**전달됨:** [operations.py](../../src/operations.py)와
[reference_guidance.py](../../src/reference_guidance.py)는 현재 파일에 결합된
관찰 보고의 계약을 제공한다. [legal_qa.py](../../src/legal_qa.py),
[plagiarism.py](../../src/plagiarism.py), [typesafe_jev.py](../../src/typesafe_jev.py)는
명시된 근거와 허용 비교군을 사용하는 별도 검토 경로다.
[법률 QA와 한계](LEGAL_QA.md)를 함께 읽는다.

**운영자가 수행:** 원화·식자·조립본의 구도, 연기, 연속성, 호흡, 조명, 식자,
원고 충실도를 실제로 보고 기록한다. 외부 판단을 사용하면 현재 서비스 조건과
해당 자료의 외부 처리 허용 범위를 확인한다. 스킬의 설치나 코드의 존재만으로
API 호출·비용·원고 또는 이미지 전송이 허용되는 것은 아니다.

**미지원:** 인터넷 전체 표절 탐색, 전면 무침해 보증, 공개되지 않은 사전학습
이력의 자료별 검증, 자동 법률 전문가 승인, 보지 않은 그림의 품질 통과.

## 7. 고지, 식별 표식과 최종 증빙

**전달됨:** [ai_notice.py](../../src/ai_notice.py)와
[package_webtoon.py](../../tools/package_webtoon.py)는 고지 검토본을 새 경로로 만든다.
[provenance_watermark.py](../../src/provenance_watermark.py)와
[mark_review.py](../../tools/mark_review.py)는 RGB PNG 사본의 실험적 픽셀 표식과 검출을
지원한다. [고지 양식](templates/notice.example.json)과
[최종 증빙 절차](PRODUCTION_RUNBOOK.md)를 사용한다.

**운영자가 수행:** 실제 AI 활용과 접수 상태에 맞는 문구 작성, 최종 파일 재검수,
표식 뒤 변경된 manifest·분할본·ZIP 해시 현행화, 사용 자료·행위·권한·검수와
최종 파일의 연결. 고지·워터마크 도구는 전달 폴더 전체의 모든 변형을 자동으로
다시 등록하거나 공개 승인하지 않는다.

**미지원:** 복제·스크린샷·타 AI 입력의 기술적 차단, 서명된 C2PA 발급, 워터마크를
통한 권리 인증. 키는 제작 기록이나 공개 파일에 포함하지 않는다.

## 8. Google Drive와 로컬 용량 정리

**운영 방법 전달됨:** [운영 절차](PRODUCTION_RUNBOOK.md),
[보관 장부 양식](templates/archive_ledger.example.json),
[실행 상태 양식](templates/run_state.example.json)은 전체 단계의 이미지·텍스트·수정
이력 연결, 전송 변형과 원본의 구분, provider readback과 로컬 정리 조건을 정한다.

**수동·환경 의존:** 계정 연결, 대상 파일·폴더 선택, 실제 업로드와 제작 이력 연결,
원격 원본 바이트 다운로드·해시 대조. Figma 반입은 필수가 아니다. 이 저장소는 Google
Drive connector 서버나 범용 업로드·원격 삭제 클라이언트를 포함하지 않는다.
작품별 업로드 스크립트와 기존 적재 영수증도 공개하지 않는다.

**완료 경계:** 폴더 목록, 로컬 동기화 표시, 작은 미리보기 또는 요약 기록만으로
전체 적재를 완료 처리하지 않는다. 원본 보관과 복구 정보가 검증되기 전 로컬
자료를 지우지 않는다. 코드 전달 시점에는 사용자의 원격 적재가 실행된 상태가 아니다.

## 9. 연구, 지식 정리와 세션 연속성

**전달됨:** [작가·연출 작업법](AUTHORING_WORKFLOW.md)은 출처 관점과 독립 적용·실제
관찰을 나누는 연구 방법을 설명한다. [세션 상태와 재개](SESSION_CONTINUITY.md)는
현재 범위·결정·유효한 해시·열린 결함·다음 단계가 긴 대화 뒤에도 남도록 한다.

**공개 자동화 범위 밖:** 기존 연구 장부의 고정 폴더·자료별 상태·노트 연결을
검사하던 전용 도구는 공개 데이터와 분리해 실행할 범용 경로로 이관하지 않았다.
공개본의 연구 운영은 출처·열람 범위·독립 가설·실제 관찰의 수동 확인이며,
과거 연구 집합 전체를 자동 재검사할 수 있다고 표시하지 않는다.

**의도적으로 제외:** 연구 원문·초록 집합·도판·표·자막 전사, 과거 대화 원문,
연구/법률/작품별 QA 장부, 계정 및 개인 지식 저장소 경로, 과거 교육 묶음 전체와
개인용 전역 스킬. 독립 메모라도 실제 내용과 재배포 범위가 검토되지 않았다면
제목이나 확장자만으로 공개하지 않는다. 폐기 원문을 인계용으로 다시 내려받지 않는다.

**한계:** 모든 선행 연구의 완독·재현·현행성 검토, 자동 context compaction,
도구가 제공하지 않는 토큰 임계값 감시는 구현되어 있지 않다. 재개 문서를 썼다는
이유로 모든 과거 대화가 복원됐다고 표시하지 않는다.

## 릴리즈 확인과 남은 실제 작업

source-only 경계는 [RELEASING](RELEASING.md)과
[public_release.py](../../tools/public_release.py)의 정확한 allowlist·내용 검사,
격리 export·ZIP·staged blob 검사로 확인한다. 코드 확장자의 파일도 작품 경로,
대사, 개인 폰트 의존성을 내용으로 검토한다. 통과한 이전 ZIP을 새 수정본의
검증 결과로 재사용하지 않는다.

포함된 테스트는 오프라인·합성 자료 또는 모의 API를 사용한다. 실제 AI 원화 한 컷,
승인된 작화와 연결 컷 비교, 모바일 관찰, 계정 연결과 원격 원본 readback,
최종 작품·공개 승인은 해당 사용 환경에서 수행하고 기록해야 한다. 제작 시간의
배수 개선은 전체 품질·검수·적재를 포함한 전후 측정이 없으면 미입증이다.
