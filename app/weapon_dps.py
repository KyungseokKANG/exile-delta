"""무기 자체 DPS (거래소 · PoB 아이템 툴팁과 같은 기준). 캐릭터 · 옵션 · 패시브와 상관없이 무기 글만 보고 계산.

  피해 종류마다 DPS = (최소 + 최대) / 2 × 초당 공격 횟수
  물리 DPS · 원소 DPS(화염 + 냉기 + 번개) · 카오스 DPS, 총 DPS = 셋의 합

아이템 글의 '물리 피해: 453-738' 같은 줄은 이미 국부 옵션(물리 피해 % 증가, 추가 피해)과 지금 퀄리티가
들어간 최종 값이라 그대로 쓴다. 퀄리티 20% 기준 물리 DPS(거래소의 'Q20')는 국부 물리 피해 % 증가를 찾아서 환산.
"""
from __future__ import annotations

import re

RANGE = r"(\d+)-(\d+)"
KEYS = {
    "phys": ("Physical Damage:", "물리 피해:"),
    "ele": ("Elemental Damage:", "원소 피해:"),
    "chaos": ("Chaos Damage:", "카오스 피해:"),
    "aps": ("Attacks per Second:", "초당 공격 횟수:"),
    "crit": ("Critical Strike Chance:", "치명타 확률:"),
}
QUALITY_RE = re.compile(r"^(?:Quality|퀄리티): \+?(\d+)%")
INC_PHYS_RE = re.compile(r"^(?:(\d+)% increased Physical Damage|물리 피해 (\d+)% 증가)(?:\s*\((?:implicit|crafted|fractured)\))?$")
LOCKED = {"Corrupted", "Mirrored", "타락", "복제"}


def _ranges(v: str) -> list[tuple[int, int]]:
    return [(int(a), int(b)) for a, b in re.findall(RANGE, v)]


def _num(v: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", v)
    return float(m.group(0)) if m else None


def calc(text: str) -> dict | None:
    """무기면 {'phys','ele','chaos','total','aps','crit','quality','q20_phys','q20_total', ...}, 무기가 아니면 None."""
    lines = [ln.strip() for ln in (text or "").replace("\r", "").split("\n")]
    found: dict[str, str] = {}
    quality = 0
    inc_phys = 0
    locked = False
    for ln in lines:
        for k, names in KEYS.items():
            for n in names:
                if ln.startswith(n) and k not in found:
                    found[k] = ln[len(n):].strip()
        m = QUALITY_RE.match(ln)
        if m:
            quality = int(m.group(1))
        m = INC_PHYS_RE.match(ln)
        if m:
            inc_phys += int(m.group(1) or m.group(2))
        if ln in LOCKED:
            locked = True
    aps = _num(found.get("aps", ""))
    if not aps:
        return None
    phys_r = _ranges(found.get("phys", ""))
    ele_r = _ranges(found.get("ele", ""))
    chaos_r = _ranges(found.get("chaos", ""))
    if not (phys_r or ele_r or chaos_r):
        return None

    def dps(rs):
        return sum((a + b) / 2 for a, b in rs) * aps

    phys, ele, chaos = dps(phys_r), dps(ele_r), dps(chaos_r)
    out = {
        "aps": aps, "crit": _num(found.get("crit", "")), "quality": quality, "locked": locked,
        "phys": phys, "ele": ele, "chaos": chaos, "total": phys + ele + chaos,
        "phys_range": phys_r[0] if phys_r else None, "ele_ranges": ele_r, "chaos_range": chaos_r[0] if chaos_r else None,
        "inc_phys": inc_phys, "q20_phys": None, "q20_total": None,
    }
    # 퀄리티 20% 기준: 물리 피해 = 기본 × (1 + 증가%) × (1 + 퀄리티%) → 퀄리티 부분만 바꿈
    if phys and quality < 20 and not locked:
        f = (100 + inc_phys + 20) / (100 + inc_phys + quality)
        out["q20_phys"] = phys * f
        out["q20_total"] = out["q20_phys"] + ele + chaos
    return out


def html_line(w: dict, dim: str = "#b5aa95") -> tuple[str, str]:
    """오버레이용 (한 줄 HTML, 툴팁). 물리 · 원소 · 카오스 중 있는 것만."""
    def n(v):
        return f"{v:,.0f}" if v >= 100 else f"{v:,.1f}"

    parts = []
    if w["phys"]:
        parts.append(f"<span style='color:{dim}'>물리</span> <b>{n(w['phys'])}</b>")
    if w["ele"]:
        parts.append(f"<span style='color:{dim}'>원소</span> <b style='color:#e8a25a'>{n(w['ele'])}</b>")
    if w["chaos"]:
        parts.append(f"<span style='color:{dim}'>카오스</span> <b style='color:#c58be0'>{n(w['chaos'])}</b>")
    multi = sum(1 for k in ("phys", "ele", "chaos") if w[k]) > 1
    head = f"<span style='color:#c8a96a; font-weight:bold'>무기 DPS</span> "
    body = " · ".join(parts) + (f" · <span style='color:{dim}'>합계</span> <b style='color:#ead197'>{n(w['total'])}</b>"
                                if multi else "")
    sub = [f"초당 {w['aps']:g}회"]
    if w.get("crit"):
        sub.append(f"치명타 {w['crit']:g}%")
    if w.get("q20_phys"):
        sub.append(f"퀄리티 20% 면 물리 {n(w['q20_phys'])}" + (f" · 합계 {n(w['q20_total'])}" if multi else ""))
    line = head + body + f"<br><span style='color:{dim}; font-size:9.5pt'>{' · '.join(sub)}</span>"
    tip = ["무기 자체 DPS: (최소 + 최대) ÷ 2 × 초당 공격 횟수 (거래소 · PoB 아이템 툴팁과 같은 기준)",
           "캐릭터 · 패시브 · 다른 장비 옵션은 빼고 무기 글에 적힌 피해와 공격 속도만 봐요."]
    if w.get("phys_range"):
        a, b = w["phys_range"]
        tip.append(f"물리: ({a} + {b}) ÷ 2 × {w['aps']:g} = {w['phys']:,.1f}")
    for e in w.get("ele_ranges") or []:
        a, b = e[0], e[1]
        nm = {"Fire": "화염", "Cold": "냉기", "Lightning": "번개"}.get(e[2], "원소") if len(e) > 2 else "원소"
        tip.append(f"{nm}: ({a} + {b}) ÷ 2 × {w['aps']:g} = {(a + b) / 2 * w['aps']:,.1f}")
    if w.get("chaos_range"):
        a, b = w["chaos_range"]
        tip.append(f"카오스: ({a} + {b}) ÷ 2 × {w['aps']:g} = {w['chaos']:,.1f}")
    if w.get("q20_phys") and w.get("inc_phys") is None:
        tip.append(f"퀄리티 20% 환산: 지금 퀄리티 {w['quality']}% → 20% 로 바꿔서 PoB 로 다시 계산한 값")
    elif w.get("q20_phys"):
        tip.append(f"퀄리티 20% 환산: 지금 퀄리티 {w['quality']}%, 국부 물리 피해 증가 {w['inc_phys']}% 기준 "
                   f"× (100 + {w['inc_phys']} + 20) ÷ (100 + {w['inc_phys']} + {w['quality']})")
    elif w.get("locked") and w["quality"] < 20:
        tip.append("타락 · 복제 아이템이라 퀄리티를 더 올릴 수 없어요.")
    return line, "\n".join(tip)
