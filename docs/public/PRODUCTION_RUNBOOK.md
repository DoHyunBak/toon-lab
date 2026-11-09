# 제작 운영과 완료 증빙

## 2026-11-03 완성본 PNG 적재 전 압축

신규 완성본의 최종 조립·실제 검수 후 Drive 적재 전에 루트 `compress_png.py`를 실행한다.
[무손실 압축 사용법과 다른 세션용 프롬프트](PNG_COMPRESSION.md)를 따른다.
`python compress_png.py "workspace/delivery/master.png" "workspace/delivery/compressed/001화 - 회차 제목.png"`

원본·기존 출력은 보존한다. 압축 영수증의 스캔라인/비-IDAT 청크 동일성과 전후 SHA-256·크기를
확인하고, 실제 Drive 원본 바이트 readback을 출력 해시·크기와 대조한다. 완성본에는 PNG만,
압축 전 원본·JSON·증빙은 작품별 백업/기록 폴더에 둔다. 용량 감소가 없어 원본을 채택해도 정상이다.
압축 실패 시 적재를 중단한다. 로컬 압축은 작품 승인·원격 검증을 대신하지 않는다.


컷 크기·호흡·실측 말풍선·꼬리·효과 배치는
[편집·식자 제작 기준](EDITORIAL_LETTERING_PLAYBOOK.md)을 따른다. 승인 사례의 판단을
현재 원고와 원화에 적용하고, 기존 회차 좌표를 복사해 품질 승인으로 취급하지 않는다.

환경 준비와 한 컷 생성은 [에이전트 이미지 제작 절차](AGENT_IMAGE_WORKFLOW.md), 원고·구도 판단은
[작가 공정](AUTHORING_WORKFLOW.md), 오류의 원인/해결은 [트러블슈팅](TROUBLESHOOTING.md)을
먼저 읽는다. 이 문서는 실제 구현과 수동 공정을 구분해 연결한다. 예제의 경로는
저장소 루트 기준이고, 작성된 작품별 입력과 기록은 Git에서 제외한다.

## 1. 원고와 공정 고정

신규 기획·구조 재작성에서는 먼저 [작가 공정의 스토리 검토](AUTHORING_WORKFLOW.md#작화-전에-이야기부터-검토한다)와
[검토 양식](STORY_REVIEW_TEMPLATE.md)을 적용한다. 현재 원고 해시와 실제 장면 근거를 연결하고
이야기의 핵심 미해결 문제가 없어야 작화를 시작한다. 이 수동 착수 조건은 `ready`의 자동
검사와 구분한다. 거절된 원고를 그림·식자 개선만으로 통과시키지 않는다.

원고 사건·장면 ID·순서·캐릭터 설정을 확인하고 새 job 디렉터리를 준비한다.
`prepare`도 원고를 복제하므로 해당 이용이 허용된 자료만 사용한다. 현재 사용자가
요청한 범위와 완료 조건을 기록하고 기존 후보·승인·거절 이력을 보존한다.

```powershell
python -m src.factory prepare workspace/local/episode.json --output-dir workspace/local/jobs/episode_v1 --characters workspace/local/characters.json
python -m src.factory adopt-workflow workspace/local/jobs/episode_v1 --record workspace/local/workflow_review.json
python -m src.factory next workspace/local/jobs/episode_v1
```

캐릭터가 없는 기술 원고는 `--characters`가 필요 없다. `adopt-workflow`의 record 구조는
인계 문서를 따른다. 실제 자료·이용 행위·모델/폰트 조건·전송 범위와 근거 파일/해시를
먼저 확인한다. 빈 형식을 작성한 것을 법률 검토 완료로 표시하지 않는다. 미해결 조건은
`holds`에 남기고, 변한 모델·입력·공정에는 이전 검토를 그대로 적용하지 않는다.

명시적으로 채택된 검토 공정과 과거 비채택 작업의 게이트는 다르다. Jev/법률 API를
매 컷 품질 승인 도구로 강제하지 않는다. 중요한 공정 변경·권리 관련 제보·구체적 의심은
허용된 최소 사실과 최신 공식 근거로 별도 검토한다. 과거 `insufficient`를 통과로
고치거나 새 문서로 소급 승인하지 않는다. [법률 QA](LEGAL_QA.md)를 함께 따른다.

## 2. 간단한 장면 계획과 시퀀스 상태

장면마다 목적·카메라·인물 위치·시선·현재 소품 상태·핵심 행동·보호 대상·대사 공간을
짧게 작성한다. 원고 사건과 편집상 배치 제안을 구분한다. 상세 AI 러프를 반복 생성할
필요가 없으며 텍스트/선 도식의 배치를 생성 지시의 텍스트로 전달한다.

원고에 결합한 시퀀스 상태는 다음 구조로 작성할 수 있다. 아래 값은 양식이며 실제
원고에 맞게 작성해야 한다. 최상위 `episode_sha256`은 job의 실제 원고 파일 바이트다.

```json
{
  "episode_sha256": "<ACTUAL_EPISODE_SHA256>",
  "shared": {
    "setting": "<APPROVED_SETTING>",
    "visual_invariants": "<APPROVED_TEXTUAL_INVARIANTS>"
  },
  "scenes": [{
    "id": "cut_001",
    "source_action": "<EXACT_CURRENT_DESCRIPTION>",
    "staging": "<POSITION_CAMERA_EYELINE>",
    "prop_state": "<CURRENT_PROP_STATE>",
    "protected_subjects": "<VISIBLE_ACTION_AND_CLUES>"
  }]
}
```

`src.production_control.compile_context`는 원고 해시, 모든 ID의 유일성·순서·누락,
각 `source_action`과 필수 문구를 확인한다. 이는 문자열/상태 검사이며 연출이 좋은지
자동 판단하지 않는다. 모든 장면을 원고 순서대로 작성해야 한다.

job 안에 `generation_context.json`을 두는 경우 그 파일의 절대 경로와 SHA-256을
실제 workflow evidence에 추가하고 검토 record를 현행화한다. `next`는 결합이 없거나
원고가 달라진 상태를 차단한다. 이미 있던 작업에 이 파일을 몰래 추가해 과거 입력을
변경하지 않는다.

```powershell
python tools/compile_production_batch.py --episode workspace/local/jobs/episode_v1/conti/episode.json --context workspace/local/jobs/episode_v1/generation_context.json --briefs workspace/local/jobs/episode_v1/prompts --output workspace/local/batch_v1.json
```

위 명령은 로컬 지시문 준비만 한다. 원화 생성·반입·품질 승인·적재는 하지 않는다.
예시의 `conti/episode.json`은 prepare가 작성한 원고다. 실제 경로는 job.json의
`episode` 필드에서 확인한다. 파일명만 맞추려고
원고 사본을 다시 만들거나 해시를 임의 갱신하지 않는다.

## 3. 생성·중단 재개·수정 이력

에이전트에 연결된 이미지 도구로 글자 없는 원화를 만든다. 컷마다 실제 도구와 모델
(제공되는 경우), 전달한 프롬프트, 허용된 입력과 생성 파일을 보존한다. 중단되면
결과 파일과 실행 기록을 먼저 확인하고, 이미 완료된 컷을 중복 생성하지 않는다.
한 컷의 작화·구도·소품을 직접 확인한 뒤 연결된 소수 컷과 회차로 확대한다.

```powershell
python -m src.factory import workspace/local/jobs/episode_v1 cut_001 workspace/local/cut001.png --prompt-file workspace/local/cut001_actual_prompt.txt --no-visual-references
```

교체는 같은 import에 `--replace`를 명시한다. 원본과 과거 검수는 history로 보존되고
현재 조립/검수는 다시 필요해진다. 별도로 만든 후보는 반입되기 전까지 current job이
아니다. `provider=imagegen`은 에이전트 이미지 도구 경로를 나타내는 기록이며,
실제 서비스의 서명·입력 권한·작품 승인을 뜻하지 않는다.

### 같은 실패를 반복하지 않는 기록

공통 결함이 보이면 확장을 멈추고 원인과 방법을 수정한다. 증상, 실제 관찰,
`failure_kind`, 수정, 재발 방지, 재검증 결과를 남긴다. 이전 correction은 attempt
이력에 보존하고 현재 실행 브리프에는 충돌 없는 최신 수정 하나만 남긴다.
`replace_correction`과 batch 컴파일러의 역할을 구분한다.

`repeated_failure`는 장면별 attempt의 `REJECTION.json`을 읽어 같은 kind의 연속
두 실패를 판별한다. **이미지 도구가 거절 기록을 자동 생성하거나 자동으로 이 함수를
호출하지는 않는다.** 현재 공개본에는 해당 기록 전체를 관리하는 범용 rejection CLI가
없다. 호출 에이전트가 실제 거절 기록을 작성하고 함수 결과를 확인하는 수동 연결이다.
없는 자동화가 있다고 보고하지 않는다.

job의 `generation_evidence/CUT.replan.json`이 있으면 `next`는 재계획을 요구한다.
새 브리프와 바뀐 방법을 검토한 뒤 `CUT.replan_resolution.json`을 작성한다.
필요한 필드는 `replan_sha256`, `revised_prompt_sha256`, `strategy`다. 현재 구현에서
후자의 prompt 해시는 `read_text(encoding='utf-8')`로 읽은 문자열을 UTF-8로 인코딩한
값이다. 파일의 raw-byte 해시와 CRLF 정규화 차이를 혼동하지 않는다.

새 prompt가 차단 당시 prompt와 같거나 해시/전략이 없으면 계속 차단된다. 상태 파일을
삭제해 우회하지 않는다. 실제 방법의 효과는 새 이미지에서 확인한다.

## 4. B/C 식자와 의미 기반 배치

신규 식자는 오픈 라이선스 폰트만 사용한다. 기본은 공식 Pretendard v1.3.9
Medium(500), 명시적 강조는 Bold(700)이며 업계 평균에 관한 통계적 주장이 아니다.
`src/font_policy.py`가 실제 파일 SHA-256과 OFL 전문을 확인한다. 환경변수·CLI·개별
대사 경로에도 적용하고 시스템 폰트 fallback은 차단한다. 다른 오픈 폰트도 출처·조건·
파일 해시를 검토해 허용목록에 등록한 뒤 사용한다. 과거 회차 전용 스크립트를 새 식자에 재사용하지 않는다.

`stitch_episode`와 `package_webtoon.py`는 실제 사용 폰트 해시/굵기를 기록하고
`font_licenses.json`, `licenses/Pretendard-OFL.txt`를 만든다. 전달 ZIP도 두 파일을
포함한다. OFL 전문을 독자 화면에 삽입하지 않는다. 소스 공개 export에는 폰트 바이너리를
포함하지 않으므로 [공식 폰트 설치 안내](FONTS.md)에 따라
두 OTF와 OFL을 먼저 준비한다. 파일이 없으면 제작을 중단하며 다른 글꼴로 대체하지 않는다.

기존 완성본·승인본은 그대로 보존한다. 과거 본문 픽셀을 보존한 재포장본은
`source_font_provenance=legacy_unverified`로 기록하고 전체가 오픈 폰트였다고 주장하지 않는다.
새 식자는 실측·줄바꿈·모바일 검수를 다시 수행하고 증빙을 새 최종 해시에 연결한다.

폰트의 실제 글자 폭·행간·타원 곡면 여백으로 몸체를 계산한다. B/C는 명시적인 연출
선택이다. 공간이 부족하면 줄바꿈·대사 분리·구도·컷 여백을 검토한다. 글자를 자동으로
줄이거나 모든 대사를 바깥 띠로 미는 것을 일반 해법으로 삼지 않는다.

대사에는 현재 장면을 보고 `art_anchor`와 `protected_art_boxes`를 지정할 수 있다.
말풍선은 빈 공간에서 장면을 덮을 수 있다. 얼굴·손·행동·단서를 가리는지 실제 이미지로
본다. 기하 충돌 검사는 연기·가독성·시선 흐름의 관찰을 대체하지 않는다.

layout은 각 current raw의 `source_image`, 실제 크기, 원고 ID/설명/대사와 일치해야 한다.
역할·시점·전환·기억군·reveal/스크롤 의도는 편집자가 작성한다. 기본 profile은 작품별
최적값을 학습한 모델이 아니다. 과거 좌표나 profile을 현재 장면에 무조건 복사하지 않는다.

```powershell
python tools/build_layout_job.py workspace/local/jobs/episode_v1 workspace/local/scene_layout_plan.json --output-dir workspace/local/layout_review_v1
python -m src.factory next workspace/local/jobs/episode_v1
```

독립 `apply_layout_policy.py` 실행은 layout 후보를 만들지만 current job에 결합하지는
않는다. 최종 job 검수에는 builder의 current raw·원고·manifest 결합을 확인한다.
기존 결과를 덮어쓰지 않고 새 출력 경로와 immutable layout snapshot을 사용한다.

## 5. 실제 검수·고지·식별·증빙

원화, 식자 컷, 전체 스크롤, 모바일 정지 화면을 직접 확인한다. 현재 review 사본에
구도·연기·연속성·호흡·조명·식자·원고 충실도의 근거를 작성하고 `review --report`로
제출한다. 원고/원화/출력 결합 해시는 수동으로 고치지 않는다. 바뀐 결과에는 재검수가
필요하다. `ready`는 사람의 작품 승인이나 공개 승인과 다르다.

고지 설정은 범용 양식을 실제 사용 방식·폰트·접수 상태에 맞춰 작성한다. 원래 전달본을
보존한 채 `tools/package_webtoon.py`로 새 내부 검토본을 만든다. 실제 접수처를 확인하지
않았다면 운영 중인 것처럼 표시하지 않는다. 내부 후보의 blockers를 문구 수정만으로
법적 승인으로 바꾸지 않는다.

`tools/mark_review.py`의 `init-key → embed → verify`는 출처 식별을 보조한다. 키는
비공개로 별도 보관한다. 복제·AI 입력 방지·C2PA 서명·권리 인증을 보장하지 않는다.
고지나 표식이 바뀌면 최종 바이트와 해시를 다시 확인한다.

최종 증빙에는 다음 실제 관계를 남긴다.

- 대상 버전, 입력 모드, 최종 master/분할/ZIP/manifest의 해시.
- 실제 사용 자료와 생성 입력·관찰 참고·QA 비교·편집 재료의 역할 구분.
- 자료/행위별 출처·조건·허용 범위·수신자·조건 이행·미확인.
- 원고 → 실제 도구/prompt/model/생성 기록 → 원본 → 편집·식자·합성 → 전달본의 연결.
- 실제 검사·수정·관찰·사람 승인·게시 결정과 각각의 보류 사항.
- 사후 정리한 사실은 backfill 표시, 알려지지 않은 seed/모델/시간은 unknown 표시.

사전학습의 공개되지 않은 자료별 권리나 인터넷 전체 유사성을 확인했다고 주장하지 않는다.
기존 산출물에 남은 불확실성은 새 공정 문서로 소급 삭제하지 않는다.

## 6. Google Drive·로컬 보관

보존된 모든 허용된 제작 단계의 이미지와 텍스트, 수정/거절본, 검수·결정·결과 연결을
작품별 Google Drive 비공개 전용 폴더에 통합한다. 요약이나 연락시트로 전체 원본 기록을 대체하지 않는다.
동일 이미지 바이트는 하나의 파일로 보관해도 모든 발생 경로와 사건을 연결해야 한다.
제작 기록 저장소 변경에 따라 Figma 반입과 노드 readback은 필수가 아니다. 과거 기록은 보존한다.

Google Drive에는 허용된 전체 원본과 증빙을 지정 비공개 폴더에 보관한다. 파일 목록,
로컬 동기화 아이콘이나 업로드 성공 응답을 원본 바이트 readback으로 바꾸지 않는다.
원격에서 다시 읽은 실제 바이트·크기·해시를 원본과 대조하고 파일/폴더 ID를 기록한다.
이미지와 텍스트의 모든 버전을 파일 ID와 해시로 연결한다. 원본과 전송본이 변환됐으면 변환 관계를
남기고 원본 검증을 별도로 완료한다. 공유 권한을 확대하지 않는다.

`templates/archive_ledger.example.json`은 장부 형식이다. **저장소에는 Google Drive connector
업로드와 provider readback을 대신 실행하는 구현이 포함되지 않는다.** 수신 에이전트가
연결된 도구와 실제 전송 권한을 확보해 수행한다. 연결이 없으면 미적재·보류 이유를
남기며 로컬 정리를 완료로 표시하지 않는다.

로컬에는 릴리즈 가능한 최종 전달본을 남기는 방향으로 정리하되, 전체 허용 원본의
적재·원본 바이트 검증·제작 이력 연결·재개 경로 확인이 끝날 때까지 임시 원본을 보존한다.
키·개인 대화 캡처·허락 없는 원문은 일반 제작 기록에 자동 전송하지 않는다.

## 7. 속도 개선의 측정

준비, 이미지 도구 대기, 원화 생성, 실제 검수, 수정, 조립, Drive 반입과 원본 검증을
별도 시각/기간으로 기록한다. first-pass 통과율·재작업률·최종 완료 컷당 시간과 함께
비교한다. 지시문 컴파일 시간이나 호출 수를 전체 제작 속도로 바꾸지 않는다.
시작·완료·재시도는 `templates/timing_events.example.json` 형식을 사용할 수 있다.
100배 단축은 목표이며 전체 공정 실증이 남아 있다. 품질·권한·검증을 생략한 값은
성공 근거가 아니다. 실패할 때마다 방법이 달라졌는지 확인하는 것이 우선이다.
