---
name: toon-production
description: Produce or revise a toon_lab episode using an agent image tool or ComfyUI, with scene planning, lettering, layout, visual review and provenance.
---

# 원고에서 검토 전달본까지

이미지 생성 도구가 연결된 에이전트는 `docs/public/AGENT_IMAGE_WORKFLOW.md`를
따라 한 컷부터 제작한다. 로컬 ComfyUI가 선택된 작업은
`docs/public/PRODUCTION_RUNBOOK.md`를 읽고 해당 절차를 수행한다. 창작을 요청받으면
아이디어로 짧은 원고를 쓰고, 샘플 요청에는 범용 예제를 사용한다.

- 시작 전에 current job/state, 원고 ID·순서·사건과 유효한 해시, 열린 결함, 실제 승인
  범위를 확인한다. 과거 완료본/거절본을 새로운 승인본으로 제시하지 않는다.
- `generation_context.json`의 선택적 `editorial`을 쓰면 원고 컷 ID·연출 이유·독자 정보·
  전후 상태·앞 장면 의존성을 실제 생성 본문에 연결한다. 선언한 상태 충돌은 생성 전에 고친다.
- 공통 결함은 `sequence_defects.json`에 영향 컷과 원인을 기록한다. `next`가 반환하는
  `resolve_sequence_defect`를 무시하지 않는다. 바뀐 prompt 해시에 묶인 한 검증 컷만
  먼저 시험하고, 실제 관찰 이미지와 수정된 영향 컷 prompt 해시를 결합해 닫는다.
- 장면 목적·시점·인물 위치·시선·소품 상태·보호 대상·대사 공간을 간단한 선 또는
  텍스트로 계획한다. 상세 밑그림 반복 생성은 필수가 아니다. 관찰용 도식 이미지를
  생성 입력으로 자동 첨부하지 않는다. 작가의 판단 질문은 `AUTHORING_WORKFLOW.md`에 있다.
- 실제 입력 모드와 모델/노드/전송 범위의 조건을 확인한다. standalone native runner와
  factory의 제한된 core text-only 반입은 다른 계약이다. 자체 원화의 예전 imagegen
  허용만으로 ComfyUI 참조를 사용하지 않는다. 구현이 없는 경로는 게이트를 우회하지 않는다.
- 원화는 대사를 제외하고 생성한다. 실제 그래프/프롬프트/모델/입출력 해시와 receipt를
  버전별로 남긴다. 먼저 한 컷, 이어 소수 연결 컷의 인물·소품·공간·호흡을 직접 검수한다.
- B/C를 명시하고 실제 폰트 크기·몸체 실측을 유지한다. 장면 위 실제 빈 공간에는
  `art_anchor`, 얼굴·손·핵심 단서에는 `protected_art_boxes`를 작성한다. 과거 좌표를
  현재 장면 관찰 없이 복사하지 않는다. 필요하면 컷 배치·여백을 바꾼다.
- 현재 raw와 원고에 결합된 `tools/build_layout_job.py`로 조립한다. 독립 layout 결과만
  만든 것을 현재 job의 식자 완료라고 기록하지 않는다. 바뀐 산출물은 검수를 새로 한다.
- 원화·식자·세로 조립·모바일 정지 화면을 직접 보고 7항목의 관찰 근거를 남긴다.
  `review.json` 결합 해시를 고쳐 통과시키지 않는다. 보지 않은 항목은 `not_reviewed`다.
- 고지·식별 표식·최종 해시·사용 자료/행위별 근거를 연결한다. 워터마크는 복제나
  다른 AI의 입력을 차단하는 장치가 아니다. 검토 공정과 무침해 인증을 혼동하지 않는다.
- 제작 이미지·텍스트·수정 이력과 원본·증빙을 `workspace/local/`에 보존한다.
  사용자가 별도 백업 대상을 지정하면 실제 원본 바이트와 복구 정보를 확인한다.

같은 실패는 `TROUBLESHOOTING.md`에서 공통 원인을 먼저 확인한다. 재계획 기록이
있으면 방법·현재 브리프·근거를 수정하고 재검증한다. 품질을 낮춰 생산량을 맞추거나
API 점수를 사람의 검수 대신 사용하지 않는다. 기술 ready, 실제 검수, 작품·공개 승인은
별개로 보고한다. 외부 전송과 게시가 이번 요청에 허용됐는지 실제 범위를 따른다.
