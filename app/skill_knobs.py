"""스킬 숫자 칸: 단계 수(Stages) · 활성 지뢰 수(Active Mines) · 토템 수(Count) — PoB 사이드바 / 젬 Count 와 같음.

상단 주 스킬 줄과 스킬 · 젬 탭이 같은 PoB 값(srcInstance)을 고치므로 한쪽에서 바꾸면 다시 계산된 결과로 양쪽이 같이 바뀐다.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QSpinBox

LABEL = {"stage": "단계 수", "mine": "활성 지뢰 수", "count": "개수"}
COUNT_LABEL = {"totem": "토템 수", "minion": "소환수 수", "skill": "개수"}
TIP = {
    "stage": "스택(단계)이 쌓이는 스킬의 단계 수 (PoB 사이드바의 Stages)\n"
             "숫자를 올리면 그만큼 쌓였을 때의 데미지로 계산해요",
    "mine": "깔려 있는 지뢰 수 (PoB 사이드바의 Active Mines)\n0 이면 PoB 기본값",
}
COUNT_TIP = {
    "totem": "이 토템 스킬을 Full DPS 에 몇 개로 셀지 (PoB 젬의 Count)\n"
             "토템 여러 개의 지속 피해가 겹치는 스킬(작열 광선 등)은 토템 수만큼 Full DPS 가 늘어요",
    "minion": "이 소환수를 Full DPS 에 몇 마리로 셀지 (PoB 젬의 Count)\n"
              "소환수 DPS 는 한 마리 기준이라, 실제로 부리는 수를 넣으면 그만큼 Full DPS 가 늘어요",
    "skill": "이 스킬을 Full DPS 에 몇 번 셀지 (PoB 젬의 Count)\n같은 스킬을 여러 개 쓰는 경우 등",
}


def label(key: str, knobs: dict | None) -> str:
    if key == "count":
        return COUNT_LABEL.get((knobs or {}).get("kind") or "skill", "개수")
    return LABEL[key]


def spins(knobs: dict | None) -> list[tuple[str, int, int, int]]:
    """[(key, value, min, max)] — 이 스킬에 보여줄 칸만."""
    k = knobs or {}
    out = []
    if k.get("stage") is not None:
        mx = int(k.get("stageMax") or 0)
        out.append(("stage", int(k["stage"]), 1, mx if mx > 0 else 999))
    if "mine" in k or k.get("mineShown"):
        out.append(("mine", int(k.get("mine") or 0), 0, 99))
    if k.get("count") is not None:
        out.append(("count", int(k.get("count") or 1), 1, 99))
    return out


def tip(key: str, knobs: dict | None) -> str:
    k = knobs or {}
    t = COUNT_TIP.get(k.get("kind") or "skill", COUNT_TIP["skill"]) if key == "count" else TIP[key]
    if key == "count":
        t += "\nFull DPS 에 넣은 스킬에만 영향이 있어요 (주 스킬 DPS 는 1개 기준)"
    if key == "stage" and k.get("stageMax"):
        t += f"\n최대 {k['stageMax']}단계"
    if key == "count" and k.get("totemLimit"):
        t += f"\n지금 최대 토템 수: {k['totemLimit']}"
    return t


def make_spin(key: str, value: int, lo: int, hi: int, on_commit, knobs: dict | None = None) -> QSpinBox:
    """값을 바꾸고 0.4초 멈추면 on_commit(key, value) — 화살표를 연달아 눌러도 계산은 한 번."""
    sp = QSpinBox()
    sp.setRange(lo, hi)
    sp.setValue(max(lo, min(hi, value)))
    sp.setToolTip(tip(key, knobs))
    sp.setKeyboardTracking(False)
    t = QTimer(sp, singleShot=True, interval=400)
    t.timeout.connect(lambda: on_commit(key, sp.value()))
    sp.valueChanged.connect(lambda _v: t.start())
    return sp
