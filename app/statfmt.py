"""DPS / EHP / 최대 피격(Max Hit) 증감 표시 공통 함수.

최대 피격은 PoB 와 같은 값(PhysicalMaximumHitTaken 등) — 물리 / 화염 / 냉기 / 번개 / 카오스 따로.
"""
from __future__ import annotations

POS, NEG, DIM = "#7fc46a", "#e0644c", "#968b7a"
# (표시 이름, PoB 출력 키, 이름 색)
MH = (
    ("물리", "PhysicalMaximumHitTaken", "#cbbd9f"),
    ("화염", "FireMaximumHitTaken", "#e8794f"),
    ("냉기", "ColdMaximumHitTaken", "#7fb4ff"),
    ("번개", "LightningMaximumHitTaken", "#f2d36b"),
    ("카오스", "ChaosMaximumHitTaken", "#c77ad6"),
)


def maxhit(st: dict) -> dict[str, float]:
    """{'물리': v, '화염': v, ...} (값이 있는 것만)."""
    return {name: st[key] for name, key, _ in MH if st.get(key) is not None}


def color_of(name: str) -> str:
    return next((c for n, _, c in MH if n == name), DIM)


def pct(a, b) -> float | None:
    if a is None or b is None or not a or abs(a) >= 1e299 or abs(b) >= 1e299:
        return None
    return (b - a) / a * 100


def fmt_big(v: float) -> str:
    a = abs(v)
    if a >= 1e299:
        return "∞"
    if a >= 1e6:
        return f"{v / 1e6:.2f}M"
    if a >= 1e4:
        return f"{v / 1e3:.1f}K"
    return f"{v:,.0f}"


def maxhit_cells(base: dict, new: dict, min_pct: float = 0.05, dim_label: bool = True) -> list[str]:
    """바뀐 최대 피격만 '화염 +3.1%' 형태로 (이름은 속성 색)."""
    a, b = maxhit(base), maxhit(new)
    cells = []
    for name, _, ncol in MH:
        p = pct(a.get(name), b.get(name))
        if p is None or abs(p) < min_pct:
            continue
        col = POS if p > 0 else NEG
        cells.append(f"<span style='color:{ncol}'>{name}</span> <b style='color:{col}'>{p:+.1f}%</b>")
    return cells


def change_cells(a: dict, b: dict) -> list[str]:
    """빌드 전체 변화 요약: DPS / EHP / 생명력 / 보호막 / 저항(%p) / 최대 피격 — 바뀐 것만."""
    if not a or not b:
        return []
    cells = []
    dk = "FullDPS" if a.get("FullDPS") and b.get("FullDPS") else "CombinedDPS"
    for key, nm in ((dk, "DPS"), ("TotalEHP", "EHP")):
        p = pct(a.get(key), b.get(key))
        if p is not None and abs(p) >= 0.05:
            cells.append(f"<span style='color:{DIM}'>{nm}</span> <b style='color:{POS if p > 0 else NEG}'>{p:+.1f}%</b>")
    for key, nm in (("Life", "생명력"), ("EnergyShield", "보호막"), ("Mana", "마나")):
        d = (b.get(key) or 0) - (a.get(key) or 0)
        if abs(d) >= 1:
            cells.append(f"<span style='color:{DIM}'>{nm}</span> <span style='color:{POS if d > 0 else NEG}'>{d:+,.0f}</span>")
    for key, nm, ncol in (("FireResist", "화염저항", "#e8794f"), ("ColdResist", "냉기저항", "#7fb4ff"),
                          ("LightningResist", "번개저항", "#f2d36b"), ("ChaosResist", "카오스저항", "#c77ad6")):
        d = (b.get(key) or 0) - (a.get(key) or 0)
        if abs(d) >= 0.5:
            cells.append(f"<span style='color:{ncol}'>{nm}</span> <span style='color:{POS if d > 0 else NEG}'>{d:+.0f}%</span>")
    mh = maxhit_cells(a, b)
    if mh:
        cells.append(f"<span style='color:{DIM}'>최대피격</span> " + " ".join(mh))
    rg = regen_cell(a, b)
    if rg:
        cells.append(rg)
    return cells


WARN = "#e8b04c"
RES = (("Fire", "화염", "#e8794f"), ("Cold", "냉기", "#7fb4ff"),
       ("Lightning", "번개", "#f2d36b"), ("Chaos", "카오스", "#c77ad6"))
ATTR = (("Str", "힘"), ("Dex", "민첩"), ("Int", "지능"))


def swap_warnings(a: dict, b: dict) -> list[str]:
    """장비 교체 시 주의할 점(HTML 줄 목록): 저항 상한 미달 · 초과 여유 감소 · 힘/민첩/지능 요구치 부족."""
    out: list[str] = []
    if not a or not b:
        return out
    for el, nm, col in RES:
        ma, mb = a.get(f"Missing{el}Resist"), b.get(f"Missing{el}Resist")
        ra, rb = a.get(f"{el}Resist"), b.get(f"{el}Resist")
        if ma is None or mb is None or ra is None or rb is None:
            continue
        cap = rb + mb
        name = f"<span style='color:{col}'>{nm} 저항</span>"
        if mb > 0 and ma <= 0:
            out.append(f"<span style='color:{NEG}'>⚠</span> {name} <b style='color:{NEG}'>상한 미달</b> "
                       f"— {rb:.0f}% / {cap:.0f}% <span style='color:{NEG}'>({rb - cap:+.0f}%)</span>")
        elif mb > ma and el != "Chaos":
            out.append(f"<span style='color:{NEG}'>⚠</span> {name} 더 부족 — {ra:.0f}% → <b>{rb:.0f}%</b>"
                       f" <span style='color:{DIM}'>(상한 {cap:.0f}%)</span>")
        elif ma > 0 and mb <= 0:
            out.append(f"<span style='color:{POS}'>✓</span> {name} 상한 채움 — {ra:.0f}% → <b>{rb:.0f}%</b>")
        elif ma <= 0 and mb <= 0 and el != "Chaos":
            oa, ob = a.get(f"{el}ResistOverCap") or 0, b.get(f"{el}ResistOverCap") or 0
            if ob < oa and ob < 15:  # 상한은 지키지만 저주·노출 등에 버틸 여유가 거의 없음
                out.append(f"<span style='color:{WARN}'>△</span> {name} 상한 유지, 초과 여유 "
                           f"{oa:.0f}% → <b style='color:{WARN}'>{ob:.0f}%</b>")
    for key, nm in ATTR:
        ha, hb = a.get(key), b.get(key)
        qa, qb = a.get(f"Req{key}") or 0, b.get(f"Req{key}") or 0
        if ha is None or hb is None:
            continue
        da, db = max(0.0, qa - ha), max(0.0, qb - hb)
        if db > da:
            out.append(f"<span style='color:{NEG}'>⚠</span> {nm} 부족 — 요구 {qb:.0f} / 보유 <b style='color:{NEG}'>{hb:.0f}</b>"
                       f" <span style='color:{DIM}'>(장비·젬 착용 불가)</span>")
        elif da > 0 and db <= 0:
            out.append(f"<span style='color:{POS}'>✓</span> {nm} 요구치 충족 — 보유 {hb:.0f} / 요구 {qb:.0f}")
    return out


def regen_cell(base: dict, new: dict) -> str:
    """생명력 재생 변화. RF 등 스스로 받는 지속 피해가 있으면 그걸 뺀 '순 재생' 기준 (음수면 경고)."""
    if not base or not new:
        return ""
    degen = (base.get("LifeDegen") or 0) > 0 or (new.get("LifeDegen") or 0) > 0
    key = "NetLifeRegen" if degen else "LifeRegenRecovery"
    a, b = base.get(key), new.get(key)
    if a is None or b is None or abs(b - a) < 1:
        return ""
    col = POS if b > a else NEG
    if degen:
        warn = f" <b style='color:{NEG}'>⚠ 생명력이 계속 줄어듦</b>" if b < 0 <= a else ""
        return (f"<span style='color:{DIM}'>순 체젠(RF 등 피해 뺀)</span> {a:,.0f} → "
                f"<b style='color:{col}'>{b:,.0f}</b>/초{warn}")
    return f"<span style='color:{DIM}'>체젠</span> <b style='color:{col}'>{b - a:+,.0f}</b>/초"


def maxhit_html(base: dict, new: dict, prefix: str = "최대 피격") -> str:
    """'최대 피격  물리 +2.0%  화염 -1.1% …  · 체젠 -42/초' 한 덩어리 (변화 없으면 빈 문자열)."""
    cells = maxhit_cells(base, new)
    rg = regen_cell(base, new)
    out = f"<span style='color:{DIM}'>{prefix}</span>&nbsp; " + " &nbsp;".join(cells) if cells else ""
    if rg:
        out = f"{out} &nbsp;·&nbsp; {rg}" if out else rg
    return out
