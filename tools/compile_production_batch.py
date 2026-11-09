"""Compile an entire sequence locally; never generate, import, or approve artwork."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.production_control import compile_context, CORRECTION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, required=True)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--briefs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Preserve previous batch')
    states = compile_context(args.episode.read_bytes(), json.loads(args.context.read_bytes()))
    rows = []
    for cut_id, state in states.items():
        brief = (args.briefs / (cut_id + '.txt')).read_text(encoding='utf-8')
        sections = brief.split(CORRECTION)
        # Preserve the newest correction only; prior instructions remain in history.
        normalized = sections[0].rstrip()
        if len(sections) > 1:
            normalized += CORRECTION + sections[-1].strip()
        text = normalized + '\n' + state + '\n'
        rows.append(dict(id=cut_id, brief=text, sha256=hashlib.sha256(text.encode()).hexdigest(),
                         old_correction_blocks=len(sections)-1,
                         current_correction_blocks=text.count(CORRECTION)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(status='prepared_not_generated_not_approved',
        context_sha256=hashlib.sha256(args.context.read_bytes()).hexdigest(), scenes=rows),
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(scenes=len(rows), output=str(args.output), model_calls=0)))


if __name__ == '__main__':
    main()
