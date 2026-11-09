# License scope and distribution boundary

The source-only toon_lab release is software, public usage documentation and
generic test/example fixtures. Project contributions in those files are
distributed under the [MIT License](../../LICENSE). MIT permits commercial use;
this document adds no noncommercial or field-of-use restriction to that license.
Preserve the applicable notices in [THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md),
including the upstream MIT notice for adapted source modules.
The [public copyright process](COPYRIGHT_SAFETY.md) describes implemented controls,
operator responsibilities and limits separately from the software license.

## Materials outside this release

The public release excludes private manuscripts, story and character settings,
reference images, generated artwork, production-specific scripts and records,
research materials, legal/audit and QA records, `.env` and other credentials,
vendor checkouts, font binaries, model weights, and runtime environments.
Private working files are not granted a license merely because they are stored
beside the public software in a development workspace.

The generic fixtures included in the release are test data for file handling,
layout or API-protocol checks. They are not an approved commercial webtoon or
evidence that a model has generated or legally cleared a work.

## Dependencies, fonts and model resources

Pillow is installed separately from `requirements.txt`; this release does not
bundle its wheel or runtime. Its MIT-CMU license and any bundled-component
notices remain applicable. A later binary/runtime distribution needs its own
inventory and retained dependency notices.

No font binary is included. Users supply a font with appropriate permissions.
If a distributor later includes a font, the font's license and notices must be
reviewed and preserved separately. The software MIT license does not relicense
a font, checkpoint, LoRA, ControlNet resource or other third-party asset.

## External services and user content

TypeSafe/Jev and image-generation providers are separate services. Users need
their own permitted access and must comply with the applicable account, service,
data-processing and input-use conditions. This software license supplies no
service credits, access credentials, downloadable model or model-weight license.
An agent skill's open-source license is distinct from the provider's service
contract. Review current official terms before submitting private materials;
do not interpret a no-training statement as a no-retention agreement.

This tool does not certify input permissions, output copyright, independent
creation, originality or non-infringement. A hash records file identity, and a
similarity judgment is a scoped screening signal. Neither is legal clearance.
Keep actual creation records and human decisions separate from model outputs.

User-supplied manuscripts, artwork and generated production outputs are not
automatically placed under MIT by using this software. Their permissions and
any protectable rights depend on the actual material, human contribution,
provider contract and applicable law. Publication or reuse of those materials
requires a separate assessment.

## 한국어 요약

공개되는 코드·사용 문서·일반 테스트 예시는 MIT 대상이며 상업적 이용을
금지하지 않습니다. 기존 제3자 고지는 유지해야 합니다. 비공개 원고·캐릭터·
그림·레퍼런스·연구/검수 기록·시크릿·폰트·모델 가중치는 공개 범위에서
제외합니다. 프로그램 사용만으로 입력 자료나 제작 결과물의 권리가 확인되거나
MIT로 전환되지는 않습니다. 외부 AI 서비스와 별도 자산의 이용 조건은 각각
확인해야 하며, 모델 검사 결과는 법적 무침해 보증이 아닙니다.
