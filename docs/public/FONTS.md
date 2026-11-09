# 신규 식자용 Pretendard

기본 대사는 Medium(500), 강조는 Bold(700)를 사용한다. 글자 크기는 장면별로 정한다.

공식 [Pretendard v1.3.9](https://github.com/orioncactus/pretendard/tree/v1.3.9)의
수정하지 않은 파일이다. 저작권자 Kil Hyung-jin, SIL Open Font License 1.1,
Reserved Font Name Pretendard. 라이선스 전문은 설치 후 `assets/fonts/pretendard/OFL.txt`에 보존한다.

| 파일 / 공식 다운로드 | SHA-256 |
|---|---|
| [Pretendard-Medium.otf](https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/packages/pretendard/dist/public/static/Pretendard-Medium.otf) | `d39e50e4bb52b4993b6a4eeb821a171254745bd824446af01e1f616b89fface0` |
| [Pretendard-Bold.otf](https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/packages/pretendard/dist/public/static/Pretendard-Bold.otf) | `2e91915fab54df71cc9598ebf608b2bdb54c6fe3c066ac61dff0bc44fca71cc7` |
| [OFL.txt](https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/LICENSE) | `d31ddd9f2bed32fd7e302a205cf2380ba0de6529152d239ef99cfb6f261bfc04` |

소스 공개 export에는 폰트 본체를 포함하지 않는다. 위 공식 파일을 프로젝트 루트의
`assets/fonts/pretendard/`에 해당 파일명으로 배치한다. 개행 변환 없이 원본 바이트를 저장한다.

`src/font_policy.py`가 파일명 대신 실제 바이트를 확인한다. 환경변수와 개별 `font_path`도 검사하고
미확인 폰트로 대체하지 않는다. 다른 폰트는 출처·조건·해시를 검토해 명시적으로 등록해야 한다.

신규 전달 폴더와 ZIP에는 `font_licenses.json` 및 저작권·OFL 전문
`licenses/Pretendard-OFL.txt`가 들어간다. 폰트 바이너리는 독자용 ZIP에 포함하지 않는다.
이는 래스터 이미지 전달에도 고지를 보존하는 프로젝트 정책이며,
[OFL FAQ](https://openfontlicense.org/ofl-faq/)의 문서/이미지 이용과 폰트 재배포 구분을 유지한다.

공개 소스에서 준비할 때는 `python tools/setup_open_fonts.py`를 실행한다. 공식 HTTPS 출처에서 위 세 파일만 받아 해시를 확인한다. 제작 중에는 자동 다운로드하지 않는다.
