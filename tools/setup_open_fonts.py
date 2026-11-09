"""Explicitly acquire pinned official Pretendard files; never run during rendering."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.font_policy import FONT_DIR, APPROVED, LICENSE_SHA256

BASE = 'https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/'
FILES = {
    'Pretendard-Medium.otf': ('packages/pretendard/dist/public/static/Pretendard-Medium.otf', next(k for k, v in APPROVED.items() if v[1] == 500)),
    'Pretendard-Bold.otf': ('packages/pretendard/dist/public/static/Pretendard-Bold.otf', next(k for k, v in APPROVED.items() if v[1] == 700)),
    'OFL.txt': ('LICENSE', LICENSE_SHA256),
}


def setup():
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='font-setup-', dir=FONT_DIR) as temporary:
        staged = []
        for name, (remote, expected) in FILES.items():
            target = FONT_DIR / name
            if target.is_symlink():
                raise ValueError('Refusing linked font file: ' + name)
            if target.exists():
                if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                    raise ValueError('Existing font asset differs; inspect it before replacement: ' + name)
                continue
            with urlopen(BASE + remote, timeout=60) as response:
                payload = response.read(4_000_001)
            if len(payload) > 4_000_000 or hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError('Official font download failed integrity check: ' + name)
            path = Path(temporary) / name
            path.write_bytes(payload)
            staged.append((path, target))
        for path, target in staged:
            os.replace(path, target)
    print('Verified Pretendard Medium 500, Bold 700 and OFL 1.1.')


if __name__ == '__main__':
    setup()
