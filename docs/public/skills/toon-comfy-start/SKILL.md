---
name: toon-comfy-start
description: Set up or verify a local ComfyUI environment for toon_lab and generate one text-only GPU smoke-test PNG. Use for a new workstation or local generation setup, including RTX 5060. Does not start a production episode.
---

# 로컬 ComfyUI 착수와 한 컷 시험

저장소 루트의 README와 `docs/public/COMFYUI_HANDOFF.md`를 읽고 실제 CLI를 확인한다.
상세 설치·그래프 계약은 그 문서가 정본이다. 사용자가 설치와 생성 실행을 요청한
범위에서 진행하며, 본편 제작으로 자동 확대하지 않는다.

1. 저장소 root/commit/변경 상태와 OS·GPU·실제 VRAM·드라이버·여유 저장공간을 확인한다.
2. 기존 정상 ComfyUI가 있으면 재사용한다. 새 설치는 최신 공식 GPU 지원 문서를
   확인해 별도 Python 환경에 한다. toon_lab `.venv`에 torch/node 의존성을 섞지 않는다.
3. ComfyUI Python에서 실제 CUDA 텐서 연산까지 확인한다. `nvidia-smi`만으로 생성
   성공이라 하지 않는다. RTX 5060 호환성을 오래된 cu126 우회 지침으로 추정하지 않는다.
4. 허용된 호환 checkpoint 하나의 출처·조건·SHA-256을 기록한다. 필요한 다운로드가
   현재 요청에 포함된 경우 공식 경로를 사용한다. 설치 권한을 유료 사용·학습·새
   외부 서비스 이용 허용으로 확대하지 않는다.
5. 기본 7노드 text-to-image 그래프와 batch=1, SaveImage 하나, PNG 한 장을 사용한다.
   모델에 맞는 해상도로 시작한다. 이번 시험에는 이미지 입력·LoRA·ControlNet·cloud
   node·custom node를 추가하지 않는다. 서버는 localhost에서 실행한다.
6. `workspace/local/`에 별도의 API JSON을 작성한다. UI `nodes/links` JSON과 구분한다.
   원고가 없으면 README 인계 문서의 중립적인 한 컷 기술 장면을 사용한다.
7. `python -m src.comfy_runner API.json --output-dir NEW --check` 뒤 `--execute`한다.
   결과는 `workflow_api.json`, `receipt.json`, `image.png`다. 완료 상태와 실제 해시를
   대조하고 이미지를 직접 연다. 중단되면 재제출 전에 `$toon-recover` 절차를 읽는다.
8. 환경 잠금과 실행 기록을 실제 값으로 남긴다. 실패 원인을 다음 시도에 반영한 뒤
   재검증한다. 한 컷이 완료되면 이미지·경로·환경·기록·다음 실행 명령을 보고한다.

결과가 실제 GPU로 생성되지 않았으면 설정/연결 확인까지만 완료로 보고한다.
성공한 기술 시험을 기존 그림체 재현·법적 인증·작품 승인으로 표시하지 않는다.
에셋·다운로드 가중치·실제 실행 기록·키를 Git에 넣지 않는다.

오류별 대응은 저장소 루트 기준 `docs/public/TROUBLESHOOTING.md`, 인계용 짧은
요청문은 `docs/public/START_PROMPT.md`에 있다. 스킬을 읽었다는 이유로 승인되지
않은 시스템 교체나 원격 업로드를 수행하지 않는다.
