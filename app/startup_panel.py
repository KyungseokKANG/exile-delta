"""시작 점검 패널: 켜자마자 프로그램 업데이트 · PoB 엔진 · PoB 새 버전 · 번역 데이터 확인을 순서대로 크게 보여준다.
모든 단계가 끝나면 몇 초 뒤 알아서 접힌다."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

SPIN = "◐◓◑◒"
LOOK = {  # 상태 → (아이콘, 색)
    "wait": ("○", "#6d6453"),
    "ok": ("✓", "#8fd08f"),
    "warn": ("!", "#ffb35c"),
    "fail": ("✕", "#ff8f78"),
}


class StartupChecks(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 0)
        box = QFrame()
        box.setObjectName("Banner")
        outer.addWidget(box)
        v = QVBoxLayout(box)
        v.setContentsMargins(18, 12, 18, 12)
        v.setSpacing(8)
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ead197;")
        v.addWidget(self.title)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(4)
        self.grid.setColumnStretch(2, 1)
        v.addLayout(self.grid)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        v.addWidget(self.bar)
        self.steps: dict[str, dict] = {}
        self._spin = 0
        self._spin_timer = QTimer(self, interval=150, timeout=self._tick)
        self._hide_timer = QTimer(self, singleShot=True, interval=5000, timeout=self._collapse)
        self.hide()

    def step(self, key: str, label: str, state: str, detail: str = "", done: int = 0, total: int = 0) -> None:
        """state: wait | run | ok | warn | fail. 같은 key 로 다시 부르면 그 줄이 바뀐다."""
        s = self.steps.get(key)
        if s is None:
            row = len(self.steps)
            icon, name, info = QLabel(), QLabel(), QLabel()
            icon.setFixedWidth(18)
            name.setStyleSheet("font-size: 13px; font-weight: bold;")
            info.setStyleSheet("font-size: 12px; color: #b8ad98;")
            info.setWordWrap(True)
            for c, w in enumerate((icon, name, info)):
                self.grid.addWidget(w, row, c)
            s = self.steps[key] = {"icon": icon, "name": name, "info": info}
        s.update(state=state, done=done, total=total)
        s["name"].setText(label)
        s["info"].setText(detail)
        self._paint_icon(s)
        self._refresh()

    def _paint_icon(self, s: dict) -> None:
        if s["state"] == "run":
            s["icon"].setText(SPIN[self._spin % len(SPIN)])
            s["icon"].setStyleSheet("font-size: 15px; color: #ead197;")
        else:
            ch, col = LOOK.get(s["state"], LOOK["wait"])
            s["icon"].setText(ch)
            s["icon"].setStyleSheet(f"font-size: 15px; font-weight: bold; color: {col};")

    def _tick(self) -> None:
        self._spin += 1
        for s in self.steps.values():
            if s["state"] == "run":
                self._paint_icon(s)

    def _refresh(self) -> None:
        running = [s for s in self.steps.values() if s["state"] in ("run", "wait")]
        if running:
            self._hide_timer.stop()
            self.show()
            if not self._spin_timer.isActive():
                self._spin_timer.start()
            self.title.setText("시작 점검 중… 잠깐만요")
            cur = next((s for s in self.steps.values() if s["state"] == "run" and s["total"] > 0), None)
            if cur:
                self.bar.setRange(0, cur["total"])
                self.bar.setValue(cur["done"])
            else:
                self.bar.setRange(0, 0)
            self.bar.show()
            return
        self._spin_timer.stop()
        self.bar.hide()
        bad = any(s["state"] in ("warn", "fail") for s in self.steps.values())
        self.title.setText("점검 끝 — 확인할 게 있어요" if bad else "점검 끝 — 모두 준비됐어요")
        self._hide_timer.setInterval(12000 if bad else 4000)
        self._hide_timer.start()

    def _collapse(self) -> None:
        self.hide()
        for s in self.steps.values():
            for k in ("icon", "name", "info"):
                s[k].deleteLater()
        self.steps.clear()
