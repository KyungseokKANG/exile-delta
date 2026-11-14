"""assets/icon.ico 생성 (빌드 시 사용)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from icon import make_pixmap  # noqa: E402

app = QGuiApplication(sys.argv)
out = ROOT / "assets" / "icon.ico"
out.parent.mkdir(parents=True, exist_ok=True)
if not make_pixmap(256).toImage().save(str(out), "ICO"):
    make_pixmap(256).toImage().save(str(out.with_suffix(".png")), "PNG")
    print("ICO 저장 실패, PNG로 저장함")
else:
    print(f"wrote {out}")
