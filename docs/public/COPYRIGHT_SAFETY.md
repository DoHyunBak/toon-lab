# 적법한 이용을 위한 제작 절차와 공개 검증 근거

## Optional authorized owned-episode reference mode

Text-only remains the default and continues to reject all image inputs. A separately prepared job may explicitly select `generation_input_mode=authorized_own_episode1_reference` only with a permission-reviewed own first-episode catalog, frozen user authorization and an approved style benchmark. Each cut declares exactly one listed reference; origin path, image and metadata hashes, authorization and actual-use IDs are checked. `next` supplies that one `referenced_image_paths` entry; omit recent-conversation-image options. Imports require the actual prompt and selected used-reference ID. This is a bounded input-use declaration, not legal clearance or a guarantee of identical art. Third-party captures and unlisted images remain excluded. Existing jobs and input histories are never relabeled. Workflow adoption, actual visual review and output-integrity checks still apply.

## Reviewed-workflow production route — 2026-10-23

A supported explicit-input-mode job can adopt a reviewed workflow with `adopt-workflow JOB --record FILE`. The record must bind actual input/use permissions, license conditions, permitted external processing and current evidence hashes. Missing/changed evidence, changed inputs or declared rights holds block progress. Operator declarations are records, not independent legal certification.

For adopted jobs, legal/similarity Jev checks are tools for workflow changes or concrete rights reports, rather than routine per-episode production approval. Actual prompt and input-use provenance, valid output and observed image review remain mandatory. `ready` reports actual old screening states unchanged and never invents a legal pass. Non-adopted compatibility jobs retain the older gates described below. Site notices must state which route is actually used.


기준일: 2026-10-21. 이 문서는 공개되는 toon_lab 소프트웨어의 원칙,
현재 코드로 확인할 수 있는 통제와 운영자가 확인할 사항을 설명합니다.
개별 작품의 권리 정리나 법률 전문가의 의견을 대신하지 않습니다.

## 공개 입장

**toon_lab은 적법하게 이용할 수 있는 입력과 라이선스 준수를 제작 원칙으로
삼습니다. 이를 위해 출처와 이용 범위의 기록, 생성·수정 이력, 지정 비교군의
유사성 선별과 별도 관찰 검토를 지원하고, 관련 법률 사전 조사·조문 인덱싱·
Jev 근거 대조·별도 검토를 필수 QA로 둡니다. 확인되지 않은 권리나 모델
판정을 법적 승인으로 취급하지 않습니다.**

이 원칙의 구현 여부를 확인할 수 있도록 소스·테스트·소프트웨어 라이선스와
제3자 고지를 함께 배포합니다. MIT가 허용하는 소프트웨어 사용권과 사용자가
넣는 원고·그림·참조 및 외부 서비스의 이용 권리는 구분합니다.
[소프트웨어 라이선스](../../LICENSE) · [제3자 출처와 고지](../../THIRD_PARTY_NOTICES.md)
· [공개/라이선스 범위](LICENSE_SCOPE.md)

## 생성 입력과 결과물 QA의 구분

신규 제작은 원고와 텍스트 프롬프트만으로 AI 원화를 생성합니다. 생성 입력에서
타인 원작과 자체 AI 캐릭터 시트·이전 생성 컷·아타리·배경·control 이미지를
모두 제외합니다. `prepare`는 해당 이미지 입력을 거절하고 텍스트 전용 mode와
정책 버전을 기록하며, `next`의 imagegen 입력에는 참조 이미지 경로나 최근
이미지 포함 옵션을 넣지 않습니다. 캐릭터와 연속성은 텍스트로 지시합니다.

생성 결과를 식자·조립·관찰하는 것, 권한 있는 이미지를 JEV 유사성 QA에서
대조하는 것은 생성 모델에 이미지를 입력하는 행위와 다릅니다. QA에서의 이미지
처리 권한은 별도로 확인합니다. 기존 참조 입력 작업은 보존하며 mode를 소급
수정하거나 과거 제작까지 텍스트 전용이었다고 표시하지 않습니다.

확인 근거: [생성 입력 계약](../../src/factory.py),
[생성 인계](../../src/operations.py), [입력 거절 테스트](../../tests/test_reference_workflow.py).

## 현재 구현된 검토·기록 기능

### 사전 조사·법률 인덱스·Jev 법률 QA

예정된 작업 행위에 대해 관련 법률을 먼저 조사하고 공식 조문의 버전·시행일·
확인일·출처와 적용할 사실/증거를 연결합니다. 생성 안내 전 `preflight`,
최종 `ready` 전 `final`에서 Jev 근거 대조와 별도 행위별 검토를 요구합니다.
누락·오류·위험·근거 부족·오래된 입력은 통과시키지 않습니다. 모델이 위험이나
근거 부족으로 분류한 결과를 운영자 수락만으로 덮지 않습니다.

외부 전송은 명시적으로 허용된 최소 사실·증거 요약과 선택 조문으로 제한하며
해당 법률 QA가 로컬 증거 파일 실물·원고·이미지를 자동 업로드하지 않습니다.
인덱스의 공식 URL·확인일·텍스트 해시는 운영자가 실제 조회하고 확인한 기록과
함께 관리해야 합니다. 코드가 링크나 선언만으로 조문 진위·최신성·모든 법률의
포괄 여부를 독립 인증하지 않습니다. 새 관할/행위/조건에는 추가 조사가 필요합니다.

게이트는 다음 작업 안내와 완료 판정에 적용되며 임의 프로그램의 실행/전송을
차단하는 OS 보안 통제가 아닙니다. 운영자 검토도 신원·변호사 자격·실제 검토의
독립 인증은 아닙니다. 기존 제작물은 이 새 절차를 소급 통과하지 않았으며,
사이트 고지문 작성과 실제 게시를 구분합니다.

확인 근거: [법률 QA 구현](../../src/legal_qa.py),
[법률 QA 테스트](../../tests/test_legal_qa.py),
[워크플로우 게이트](../../src/operations.py),
[절차와 사이트용 고지](LEGAL_QA.md).

### 텍스트 전용 선언과 과거 참조 기록

신규 작업은 `generation_input_mode=text_only`, `generation_policy_version=text-only-v1`과
실제 프롬프트, 명시적 이미지 미사용을 기록합니다. 과거 mode가 없거나 참조 입력이
포함된 작업은 새 텍스트 전용 생성으로 조용히 재사용하지 않습니다. 기존 생성물,
참조 계획과 실제 사용 선언, 원본/반입 파일의 해시와 버전 이력은 보존합니다.

운영자의 사용 선언과 로컬 파일 기록은 모델 제공자의 서명된 실행 영수증이
아닙니다. `provider=imagegen`이나 mode 값만으로 실제 호출을 독립 인증하지 않습니다.
확인 근거: [factory](../../src/factory.py), [생성 인계/출처 확인](../../src/operations.py),
[텍스트 전용 워크플로우 테스트](../../tests/test_reference_workflow.py).

### 이용 권한 선언과 외부 전송

Jev 비교군에는 범위, 외부 처리 허용 선언, 전체/개별 자료의 권리 근거가
있어야 합니다. 비어 있거나 외부 처리 허용이 없는 비교군은 요청 전에
거절합니다. 실제로 보낼 대상 원고와 비교 자료 모두의 권한은 담당자가
확인해야 합니다.

`rights_basis` 문자열과 허용 값의 존재를 검사하는 것은 라이선스·권리자의
진위를 자동 인증하는 기능이 아닙니다. 구매·공개 URL·GPT 생성·작은 캡처라는
사실만으로 필요한 모든 행위가 허용됐다고 처리하지 않습니다. 조사/저장,
외부 분석, 생성 참조, 편집과 상업 공개의 허용 범위를 나누어 확인합니다.
확인 근거: [비교군/검사 구현](../../src/plagiarism.py),
[권한 선언·오류·누락 회귀 테스트](../../tests/test_plagiarism.py).

### 지정 비교군의 유사성 선별

Jev는 제공한 이미지/컷 텍스트에서 구체적 표현의 유사성 후보와 검토할 타일을
선택합니다. 일반 장르·화풍·포즈·연출 기법과 구체적 표현을 구분하도록
질문을 구성합니다. 이 이미지 선별은 법률 QA와 별도이며 소유권·이용허락·
침해 의도를 인증하거나 적법성을 확정하지 않습니다.

현재 코드는 검사 대상·원고·식자 출력·비교 자료·정책·고정 모델을 결합해
기록하고, 비교쌍/타일 누락·오류·불확실성·검사 뒤 변경을 확인합니다.
확률이나 confidence를 표절률로 표시하거나, 낮은 신호를 인터넷 전체의
무유사성 인증으로 사용하지 않습니다. Jev의 이미지 기능은 공급자 기준
미리보기 기능입니다. 한국어 웹툰에서의 유사성 선별 정확도는 별도 검증이
필요하며, 법률 판단을 대신하지 않습니다.
[Jev 이미지 공식 문서](https://docs.typesafe.ai/images)

확인 근거: [비교 구현](../../src/plagiarism.py), [API 어댑터](../../src/typesafe_jev.py),
[모의 API 계약 테스트](../../tests/test_typesafe_jev.py).

### 별도 관찰 보고서와 변경 확인

현재 출력의 시각 검수와 Jev 비교 결과의 별도 관찰 보고서가 다음 단계에
필요합니다. 보고서는 해당 이미지/원고/출력·검사 결과에 결합되고, 수정이나
누락이 있으면 과거 결과를 그대로 통과로 쓰지 않습니다. 검사 실패나 미완료를
수동 승인으로 덮지 않습니다.

관찰자 이름·판단·메모는 운영자가 제출하는 기록입니다. 현재 로컬 CLI는
사람의 신원이나 실제로 관찰했다는 사실을 독립 인증하지 않습니다.
기술 `ready`, 에이전트 관찰, 사람의 작품 승인과 상업 공개 권한은 다른 상태입니다.
확인 근거: [워크플로우 게이트](../../src/operations.py),
[관찰 제출/오래된 결과 거절](../../src/plagiarism.py),
[단계별 차단 테스트](../../tests/test_operations.py).

## 사람이 확인하는 제작 원칙과 현재 자동화의 경계

기획·생성 전에 출처/권한과 특정 작품의 구체적 표현을 옮기는 입력인지
확인하고 필수 법률 QA를 수행하며, 생성·편집 후 실제 결과를 관찰합니다. 의심되는
사안은 허락·예외·계약과 표현의 실제 관계를 검토하고 필요시 법률 전문가에게
넘깁니다. 모델에 공개·삭제·폐기·제재 권한을 주지 않습니다.

법률 QA는 제시한 행위·사실·조문·증거의 범위를 대조합니다. 기획/생성 전의
모든 권리를 자동 인증하거나 웹툰·웹소설 전체와 모든 법률을 상시 조사하는
기능은 아닙니다. 실제 클린룸 접근 격리, 운영 서비스의 제보 접수,
법정 중단/재개, 중앙 공개 승인 및 폐기 집행 시스템도 이 소스 릴리즈에
구현된 기능으로 표시하지 않습니다. 도입 계획은 실제 구현·검증 후 갱신합니다.

일반 제보와 해당 법정 요건을 갖춘 중단 요구/명령은 구분해야 합니다.
적용되는 법정 조치를 모델 검사나 전체 증거 복사의 대기열에 묶지 않는
운영 설계가 필요합니다. 이 문서는 현재 서비스가 법정 절차를 운영하고
있다거나 특정 신고·재개 기한을 보장한다고 주장하지 않습니다.

## 공개할 증거와 비공개로 보호할 자료

공개 가능한 근거는 소프트웨어 출처/라이선스, 기능과 테스트, 검토 절차,
검사 범위·한계, 공개 패키지의 파일 목록/해시 등입니다. 실제 원고·생성 원본·
프롬프트·편집/검수 기록은 비공개 작업 공간에 보존될 수 있으며, 필요한 경우
권한 있는 담당자에게 적법한 범위로 설명합니다.

원작 캡처·비공개 원고·개인정보·원계약·비밀키를 검증 증거라는 이유로
오픈소스 저장소에 올리지 않습니다. 이 릴리즈의 일반 예시2개는 기술 테스트
자료이며 실제 제작물이나 모델 성능/권리 검증의 증거가 아닙니다.

해시는 파일 동일성을 확인합니다. 단독으로 저작자·창작 시점·독립 창작·
이용허락을 증명하지 않습니다. 로컬 해시/장부를 신뢰할 수 있는 제3자의
전자서명·시각인증처럼 설명하지 않습니다. 공개 테스트는 합성 입력·모의
응답으로 제어 흐름을 검증하며 모든 저작물의 침해 여부를 검사한 결과가 아닙니다.

출처/검수 기록을 남긴다는 원칙도 모든 자료의 무기한 보존을 뜻하지 않습니다.
목적·권한·개인정보·분쟁 보존 필요성을 구분합니다. 외부 업체의 비학습 정책을
무보관 약정으로 간주하지 않으며 실제 계정/계약의 처리 조건을 확인합니다.

## 소스 공개의 검증 절차

공개본은 검토한 파일의 명시적 허용 목록으로 별도 export합니다. 내부 문서·
작품별 스크립트·원고·이미지·연구/검수 기록·개발자 설정·비밀키를 제외하고,
독립된 공개용 환경변수 템플릿을 사용합니다. 파일 이름이 코드나 example이라는
이유만으로 안전하다고 판단하지 않습니다.

검사기는 링크/재파스 경로, 비밀값 패턴과 로컬에서 알고 있는 키,
실제 staged blob, ZIP 파일 목록·숨은 메타데이터·해시를 확인합니다.
소프트웨어/소스 변경 뒤에는 새 패키지를 검사하고, 의존성 검사와 격리된
공개본 테스트를 구분합니다. 이 검사는 파일/기록의 검증이며 권리의 진위나
모든 비밀값 부재를 보증하지 않습니다.

확인 근거: [공개 허용 목록](../../public-release.json),
[공개 검사기](../../tools/public_release.py),
[유출/변조 회귀 테스트](../../tests/test_public_release.py),
[릴리즈 절차](RELEASING.md), [보안 정책](../../SECURITY.md).

## 권리 문제의 확인과 정정

문제가 제기되면 대상 소스/제작물의 정확한 버전과 표현, 출처·권한·검수 기록을
확인하고 실제 근거에 따라 정정·수정·필요한 배포/공개 조치를 판단하는 원칙을
따릅니다. 신고만으로 침해를 확정하거나 모델 점수만으로 자료를 폐기하지 않습니다.
서비스에서 제거하는 조치와 적법하게 보존할 증거의 삭제는 구분합니다.

연락은 프로젝트에 실제로 공지된 경로를 사용하며 민감 자료를 공개 이슈에
붙이지 않습니다. 아직 설치·검증하지 않은 제보 포털이나 회신 SLA를 제공
중이라고 표시하지 않습니다. 배포 시에는 실제 연락 경로와 담당 체계를 확인합니다.

## 공식 참고 자료

- [한국저작권위원회 결과물 분쟁 예방 안내서](https://www.copyright.or.kr/gov/nuri/view.do?brdctsno=54252): 공식 지침이며 개별 사건의 법률상 면책 허가는 아닙니다.
- [국가법령정보센터 저작권법](https://www.law.go.kr/법령/저작권법): 실제 적용 시점의 조문과 사실관계를 확인합니다.
- [OpenAI 개인용 약관](https://openai.com/ko-KR/policies/terms-of-use/): 입력 권한과 출력 귀속의 범위가 있으며 실제 사용 상품/계약은 별도 확인합니다.
- [TypeSafe 고객 계약](https://typesafe.ai/legal/mca): 외부 처리·이용 조건을 실제 계정/계약에 맞춰 확인합니다.

안내서·서비스 계약·법률의 효력과 적용 대상은 다릅니다. 이 문서는 MIT에
비상업·사용 분야 제한을 추가하지 않으며, 개별 자료나 외부 서비스의 권리를
MIT로 재허락하지 않습니다.

## English summary

The non-adopted compatibility route requires researched and indexed legal evidence, scoped Jev risk screening
and separate action reviews before generation handoff and final readiness.
It also supports source/use declarations, creation and edit records, scoped
similarity screening, separate observations and freshness/coverage checks.
Its source, tests, software license and
third-party notices make those mechanisms inspectable.

Permission declarations and reviewer fields are operator records, not independent
license verification, identity attestation or legal clearance. The release does
not certify individual productions, model training data, worldwide originality,
creation time or retrospective clean-room independence. The legal QA uses supplied
facts and indexed provisions; it does not independently discover or certify every
applicable law. OS isolation and some service-level controls remain guidance or future work rather than
implemented features. Private production evidence and credentials are not included
in the public source release. Consult the current provider terms and applicable
law before processing or publishing third-party materials.
