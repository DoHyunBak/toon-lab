# 범용 기록 템플릿

이 폴더의 파일은 미작성 양식입니다. 복사본을 `workspace/local/` 등 비공개 작업
경로에 두고 실제 값으로 작성합니다. 빈 값, placeholder, `not_reviewed`를 통과
증빙으로 사용하지 않습니다. 작성된 작품 프롬프트·경로·해시 장부는 Git 대상이 아닙니다.

- `environment.lock.example.json`: Python·Pillow 버전, 이미지 도구·모델 정보, 폰트의 출처/조건/해시.
- `run_state.example.json`: 현재 단계, 생성 기록, 7항목 관찰, 결함, 승인과 재개.
- `timing_events.example.json`: 준비·대기·생성·검수·수정·적재의 실제 시간 사건 양식.
- `archive_ledger.example.json`: 원본별 Drive 파일/폴더 ID, 제작 이력 연결, 전송 변환, 원본 readback과 미반입.
- `notice.example.json`: 800px AI 고지 검토본 설정. 실제 사용한 제작 방식과 접수 상태를
  확인해 수정하고 권한이 있는 폰트를 `workspace/local/fonts/`에 준비합니다.

```powershell
python tools/package_webtoon.py workspace/local/layout_review_v1/manifest.json --output-dir workspace/local/notice_review_v1 --notice workspace/local/notice.json
```

고지·워터마크를 넣으면 최종 파일 해시가 달라집니다. 기존 원본과 검수 기록을
덮어쓰지 말고 새 결과를 직접 확인한 뒤 최종 해시에 증빙을 연결합니다. 도구가
표시하는 `internal_review_candidate`는 공개 승인이나 적법성 인증이 아닙니다.
