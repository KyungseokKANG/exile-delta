"""번역 사전 생성 (실제 코드는 app/dict_builder.py — 앱의 자동 갱신과 같은 코드)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import dict_builder  # noqa: E402

dict_builder.ROOT = ROOT
dict_builder.CACHE = ROOT / "tools" / ".cache"
dict_builder.OUT_DIR = ROOT / "data"

if __name__ == "__main__":
    dict_builder.main()