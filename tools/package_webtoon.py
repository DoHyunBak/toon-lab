"""Create a notice-first internal review copy; never publish or bypass work QA."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ai_notice import DEFAULT_NOTICE, package_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--notice", default=DEFAULT_NOTICE, type=Path)
    parser.add_argument("--report-channel")
    args = parser.parse_args()
    print(json.dumps(package_review(args.manifest, args.output_dir, notice=args.notice,
                                    report_channel=args.report_channel), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
