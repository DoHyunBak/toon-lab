# 법률 QA 절차와 사이트 고지

## Optional authorized owned-episode reference mode

Text-only remains the default and continues to reject all image inputs. A separately prepared job may explicitly select `generation_input_mode=authorized_own_episode1_reference` only with a permission-reviewed own first-episode catalog, frozen user authorization and an approved style benchmark. Each cut declares exactly one listed reference; origin path, image and metadata hashes, authorization and actual-use IDs are checked. `next` supplies that one `referenced_image_paths` entry; omit recent-conversation-image options. Imports require the actual prompt and selected used-reference ID. This is a bounded input-use declaration, not legal clearance or a guarantee of identical art. Third-party captures and unlisted images remain excluded. Existing jobs and input histories are never relabeled. Workflow adoption, actual visual review and output-integrity checks still apply.

## Reviewed-workflow production route — 2026-10-23

A supported explicit-input-mode job can adopt a reviewed workflow with `adopt-workflow JOB --record FILE`. The record must bind actual input/use permissions, license conditions, permitted external processing and current evidence hashes. Missing/changed evidence, changed inputs or declared rights holds block progress. Operator declarations are records, not independent legal certification.

For adopted jobs, legal/similarity Jev checks are tools for workflow changes or concrete rights reports, rather than routine per-episode production approval. Actual prompt and input-use provenance, valid output and observed image review remain mandatory. `ready` reports actual old screening states unchanged and never invents a legal pass. Non-adopted compatibility jobs retain the older gates described below. Site notices must state which route is actually used.


기준일: 2026-10-21. 이 문서는 toon_lab의 필수 법률 QA, 공개할 설명,
운영자가 확인해야 할 범위를 정합니다. 개별 작품의 적법성 인증서는 아닙니다.
[전체 공개 원칙](COPYRIGHT_SAFETY.md) · [구현](../../src/legal_qa.py)
· [테스트](../../tests/test_legal_qa.py)

## 생성 입력의 확정 범위

신규 생성은 텍스트 프롬프트만 사용합니다. 타인 원작뿐 아니라 자체 AI 캐릭터
시트·이전 생성 컷·아타리·배경·control 이미지까지 모든 이미지 입력을 제외합니다.
`prepare`는 이 입력을 거절하고 `generation_input_mode=text_only` 및
`generation_policy_version=text-only-v1`을 기록합니다. imagegen에는
`referenced_image_paths`와 `num_last_images_to_include`를 전달하지 않습니다.

이 제한은 원화를 생성하는 모델 입력의 규칙입니다. 생성 결과 이미지의 반입·식자·
조립·관찰, 권한 있는 비교 이미지로 수행하는 JEV 유사성 검사는 별도 단계입니다.
레거시/참조 기반 작업은 보존하고 새 텍스트 전용 작업으로 준비합니다. 새 mode를
붙여 과거 제작까지 텍스트 전용으로 소급 표시하지 않습니다.

## 사이트용 고지 문안

아래 문안은 이 절차를 실제 운영하는 사이트에 게시할 문안입니다. 문안을
저장하거나 소스에 포함하는 것과 사이트 게시·운영 검증은 구분합니다.
적용하지 않은 과거 제작물에 검사 완료 표시를 붙이지 않습니다.

> 우리는 원고와 텍스트 프롬프트만으로 AI 원화를 새로 생성하고, 자체 생성
> 캐릭터 시트·이전 컷을 포함한 모든 이미지를 생성 모델 입력에서 제외합니다.
> 결과물을 자체 검토하고 구체적 표현의 유사성이 의심되면 추가 대조합니다.
> 웹툰 제작 과정의 법적 위험을 줄이기 위해 작업 전 관련 법률을
> 조사하고, 공식 조문과 적용 시점·출처를 행위별로 인덱싱합니다. 이를
> 필요한 사실·권한 근거와 연결해 Jev로 위험과 근거 부족을 검토하고,
> 담당자가 결과를 별도로 확인하는 절차를 필수 QA로 운영합니다.
>
> 자료와 생성 결과가 변경되면 관련 검토를 갱신하며, 미확인·위험·오류가
> 남은 단계는 보류하고 보완합니다. 생성 후에는 지정 비교군의 표현 유사성
> 검토와 실제 이미지 관찰도 수행합니다. 외부 분석에는 처리 권한을 확인한
> 최소 자료만 사용하고, 원작 캡처·비공개 원고·개인정보·계약서·비밀키를
> 공개 증빙으로 게시하지 않습니다.
>
> Jev는 제공된 사실과 법률 근거를 대조하는 보조 도구입니다. 검사 결과는
> 법률 전문가의 의견이나 적법성·무침해 보증을 뜻하지 않습니다. 검사 범위,
> 운영자가 확인한 사항과 남은 한계를 구분해 설명하며 필요한 추가 검토를
> 거쳐 공개 여부를 결정합니다.

사이트의 실제 운영 상태·대상 작품 범위와 이 설명이 다르면 게시 전에
문안을 수정해야 합니다. 이 소스 변경만으로 사이트 배포나 기존 제작물의
법률 QA가 완료되었다고 주장하지 않습니다.

## 실행 순서

1. **예정 행위 조사:** 자료 수집/보유, 텍스트 생성 입력, 외부 QA 분석, 편집/합성,
   배포/상업 공개에서 대상·목적·수신자·관할·행위 시점을 정합니다.
   저작권/라이선스, 개인정보, 초상·명예, 청소년, 광고/배포, 오픈소스,
   외부 서비스 조건의 적용 또는 비적용 이유를 기록합니다. 추가 쟁점도
   조사하며 이 목록을 모든 법률의 완전한 목록으로 취급하지 않습니다.
2. **공식 근거 인덱싱:** 공식 법령명·조항·버전·시행일·확인일·URL과 필요한
   조문 문맥을 기록하고 대상 행위/사실/증거에 연결합니다. 예외·위임 규정,
   계약의 별도 조건과 미확인을 살핍니다. 실제 적용 시점의 조문을 확인하며
   URL·해시·작성자 선언만으로 현행성이나 권리의 진위를 인증하지 않습니다.
3. **사전 QA:** `prepare` 후 `preflight` Jev 검사와 별도 행위별 검토를
   완료합니다. `next`는 이 결과가 유효할 때 생성 입력을 안내합니다.
4. **제작과 관찰:** 실제 프롬프트·이미지 미사용·생성·수정을 기록하고 그림·식자·
   연속성을 관찰합니다. 기존 지정 비교군의 Jev 이미지 유사성 검사와
   관찰 검수는 별도로 수행합니다.
5. **최종 QA:** 현재 결과와 근거에 대해 `final` 검사와 별도 검토를 완료한
   뒤 `ready`를 확인합니다. `ready`는 사람의 작품 승인이나 상업 공개
   허가를 대신하지 않습니다.

```sh
python -m src.factory legal-check JOB --index LAW_INDEX.json --stage preflight --max-requests 25
python -m src.factory legal-review JOB --report PREFLIGHT_REVIEW.json --stage preflight
```

제작·시각·유사성 검수 후 같은 두 명령의 `--stage`를 `final`로 바꾸고,
최종 검사에서 생성한 별도 보고서를 제출합니다. Windows에서는
`factory.ps1`로 같은 인수를 전달할 수 있습니다.

`legal-check`만 명시적으로 Jev 외부 API를 호출합니다. `next/status`는
로컬 기록만 확인합니다. 이 QA 게이트는 생성 안내와 완료 판정에 적용되며,
개별 반입/조립/복구 명령이나 임의 외부 도구를 차단하는 OS 보안 통제는
아닙니다. 에이전트와 운영자는 직접 호출로 절차를 우회하지 않습니다.

## 인덱스와 입력의 책임

현재 인덱스는 대한민국(`jurisdiction: KR`)과 실행일 기준 검토를 사용합니다.
`as_of`와 `checked_on`은 해당 한국 날짜여야 하며 법령 버전·시행일·
실제 적용 시점의 관계는 운영자가 검토합니다. 다른 관할이나 별도 과거 사건
판단을 이 형식에 억지로 맞춰 통과시키지 않습니다.

`sources`는 `id`, `law_name`, `article`, `version`, `effective_on`,
`checked_on`, `official_url`, `text`, `text_sha256`을 기록합니다.
공식 조문 URL은 HTTPS 국가법령정보센터 주소를 사용하고 인증 정보가 들어간
API 요청 URL은 저장하지 않습니다. 조문 내용은 대조에 필요한 문맥을
포함해야 하며 해시는 그 UTF-8 `text`에 대한 SHA-256입니다. 법령 원문과
운영자의 적용 해석·사실 주장을 섞지 않습니다.

`actions`의 각 행위에는 `id`, `stages`, `description`, `facts`,
`law_ids`, `evidence`가 필요합니다. `law_ids`는 인덱스 출처 ID에 연결하고,
각 증거는 `id`, 인덱스 기준 로컬 상대 `path`, 실제 파일 `sha256`,
외부 전송이 허용된 최소 `summary`, `external_processing_allowed`,
`rights_basis`를 갖습니다. 증거 파일 실물은 로컬에서 해시로 확인하고
이 법률 QA 요청에는 자동 업로드하지 않습니다.

최상위 `scope`, `external_processing_allowed: true`, `rights_basis`와
`coverage`도 필요합니다. `coverage`는 `copyright`, `privacy`,
`personality_defamation`, `youth`, `advertising_distribution`,
`oss_license`, `external_processing`별로 `status`(`applicable` 또는
`not_applicable`), `reason`, 관련 `action_ids`를 기록합니다. 적용되는
항목은 해당 행위에 연결하고, 비적용도 구체적 이유를 적습니다. 빈 범위나
형식적인 비적용 선언으로 발견한 위험을 누락하지 않습니다.

위 필드와 해시의 존재는 내용이 참이거나 허가가 유효하다는 증명이 아닙니다.
관련 법률의 발굴·정확한 조문 선택·사실/권한 확인·민감 정보 최소화는
담당자의 책임입니다. 새로운 행위·해외 수신자·공개 방식·계약 조건이 생기면
범위와 근거를 다시 검토합니다. 개인정보/비밀키나 허락 없는 원문·캡처를
법률 QA 입력에 넣지 않습니다. 비식별이라고 적는 것만으로 비식별 처리가
확인되는 것은 아닙니다.

## 모델 결과, 별도 검토와 변경

Jev는 제공된 행위·사실·증거 요약·조문을 좁은 질문으로 대조하고 고정된
선택지와 확률을 반환합니다. 설명을 생성한 것처럼 모델의 이유를 꾸미지
않습니다. 확률이나 confidence를 적법 확률·법률 정확도·무침해율로 표시하지
않습니다. [Choice 계약](https://docs.typesafe.ai/primitives/choice)과
[인용 근거 대조 패턴](https://docs.typesafe.ai/cookbooks/citation_check)을
따르며, 예제의 임계값을 법률 QA 성능 검증으로 사용하지 않습니다.

`not_checked`, `stale`, `error`, `blocked`는 진행 조건을 충족하지 못한
상태입니다. 위험/근거 부족·불확실한 동률·0 confidence는 보완 후 재검사하며
수동 수락으로 덮지 않습니다. `screened`도 최종 통과가 아닙니다. 모든
행위를 별도로 확인한 보고서가 현재 결과와 결합되어야 `passed`가 됩니다.

검사 완료 시 생성한 `legal_preflight.review.template.json` 또는
`legal_final.review.template.json`의 사본에 `reviewer`, `decision`,
`notes`와 모든 `action_reviews`의 `decision/note`를 작성합니다.
제출 가능한 판단은 `accept` 또는 `needs_fix`이고, 결합된 `check_sha256`을
직접 고쳐 오래된 보고서를 새 검사처럼 만들지 않습니다. 담당자 이름과
판단은 운영자 기록이며 사람의 신원·변호사 자격·실제 검토를 독립 인증하지
않습니다. 필요한 전문 검토와 공개 결정은 별도로 남깁니다.

보고서는 입력/조문/증거/정책/고정 모델의 해시, 행위 ID와 모델 결과를
기록합니다. 법률 QA 보고서에 전송 payload나 원계약/원고 사본·키를
중복 저장하지 않습니다. 동일 입력의 완료된 요청은 재실행에서 재사용할 수
있지만 누락/오류는 완료로 간주하지 않습니다. 법률 확인일이나 입력·증거가
변경되면 새 검사가 필요합니다. 사전 QA와 최종 QA는 각 단계의 관련 입력에
결합하며 최종 결과가 바뀌면 최종 검사를 갱신합니다.

## 공개 범위와 현재 적용

공개할 것은 절차·소스·테스트·검사 범위/한계입니다. 실제 계약·개인정보·
비공개 원고·원작 캡처·작품별 원본 증거는 공개 소스에 넣지 않습니다.
기존 연구 원문 폐기 정책을 되돌리거나 폐기 자료를 복원하지 않습니다.

이 소스의 모의 테스트는 통과/보류/오류/변경 경로를 검증합니다. 모든 실제
제작물의 법률 검토나 한국 법률 분야의 모델 성능 검증으로 표시하지
않습니다. 기존 작품에 새 QA를 소급 적용했다고 기록하지 않으며, 사이트
게시 여부는 별도의 실제 배포 기록으로 확인합니다.

## English summary

For non-adopted compatibility jobs, legal QA is a required step before generation handoff and final readiness:
research potential issues, index dated official provisions, compare authorized
minimal facts/evidence with those provisions using Jev, and submit a separate
action-by-action review. Missing, stale, failed, risky or insufficient evidence
does not pass. Changes require the affected review to be refreshed.

The model supports scoped risk assessment; it does not certify legality,
worldwide originality, complete legal coverage or a lawyer's approval. The gate
controls workflow handoff/readiness, not arbitrary operating-system activity.
Private evidence stays outside the public source release. Preparing this notice
does not publish a website or retrospectively approve existing productions.
