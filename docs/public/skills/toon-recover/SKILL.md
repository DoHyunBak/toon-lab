---
name: toon-recover
description: Resume interrupted toon_lab work or diagnose repeated production failures using receipts, hashes, review state and replan records. Use after a timeout, crash, handoff or context compaction; prevent duplicate generation and stale approvals.
---

# 상태를 확인하고 중복 없이 재개

저장소 루트 기준 `docs/public/SESSION_CONTINUITY.md`와 증상에 맞는
`docs/public/TROUBLESHOOTING.md`를 읽는다. 사용자와 현재 목적·범위를 맞추고 기존
파일을 지우거나 완료 표시를 고치는 것으로 시작하지 않는다.

## ComfyUI 실행이 중단된 경우

1. 실제 workflow snapshot, receipt, server origin, output node, prompt_id, 존재하는
   출력과 해시를 확인한다. 원본 graph나 서버가 바뀌었으면 같은 실행으로 재개하지 않는다.
2. `completed`면 로컬 출력 바이트와 receipt를 검증한다. 새 GPU 제출은 하지 않는다.
3. prompt_id가 기록된 미완료 실행은 동일 입력/서버/출력 경로로 runner `--resume`을
   사용한다. 이는 기존 history 조회/다운로드이며 새 POST가 아니다.
4. `submission_unknown` 또는 prompt_id가 없으면 queue/history와 수신 여부를
   조사한다. receipt에 임의 ID를 넣거나 같은 POST를 자동 반복하지 않는다. 수신 여부를
   확인할 수 없으면 보류 사실과 다음 조치를 남긴다. 다른 사용자의 작업을 취소하지 않는다.
5. receipt에 없는 출력이 이미 있으면 보존·검증부터 한다. 덮어쓰기 재시도를 하지 않는다.

## 장면/식자/공정의 반복 실패

- current job의 원고·브리프·원화·조립·검수·workflow evidence 해시와 `next/status`를
  대조한다. 실제 생성 기록과 별도 후보를 구분한다.
- 증상, 실제 관찰 근거, 확인한 원인과 남은 가설, 변경, 재발 방지, 재검증을 기록한다.
  과거 수정 지시는 이력에 보존하고 현재 실행에는 충돌 없는 최신 수정만 남긴다.
- 재계획은 해시와 실제 바뀐 방법에 결합한다. `pending_replan` 차단을 해제하기 위해
  상태만 지우거나 같은 프롬프트의 해시를 새것처럼 적지 않는다. 형식 검사는 새 방법의
  효과나 시각 품질까지 보증하지 않는다.
- 변한 결과에 과거 검수를 재사용하지 않는다. 후보를 current job에 반입·결합하는
  단계와 실제 시각 검수를 각각 수행한다. 원인 없는 재생성부터 시작하지 않는다.

## 컨텍스트 인계

실제 진행 기록은 무시되는 `workspace/local/`에 남긴다. 목표·확정 결정/제약·열린
문제·다음 한 단계와 job/receipt/hash 위치를 짧게 정리한다. 대화 원문이나 키를
Git에 복사하지 않는다. 클라이언트가 compact를 제공하면 컨텍스트가 부족해지기 전에
사용하되, 사용할 수 없는 도구나 정확한 토큰 임계값을 자동 실행했다고 주장하지 않는다.
