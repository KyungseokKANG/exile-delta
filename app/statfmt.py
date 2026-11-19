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
    keys = [(dk, "DPS")]
    fp = pct(a.get(dk), b.get(dk))
    if dk == "FullDPS" and (fp is None or abs(fp) < 0.05):
        keys.append(("CombinedDPS", "주 스킬 DPS"))  # Full DPS 에 안 들어가는 주 스킬(단계 수 등)만 바뀐 경우
    for key, nm in (*keys, ("TotalEHP", "EHP")):
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


# ---------------------------------------------------------------- RF 등 스스로 받는 지속 피해
# 전부 PoB 값 그대로 (사이드바 Total Degen / Net Life · ES · Mana Recovery).
# PoB 는 보호막 재생이 있으면 지속 피해를 보호막이 받고(뚫는 몫만 생명력), 없으면 생명력이 다 받는다.
POOLS = (("Life", "생명력", "#e07a6a"), ("EnergyShield", "보호막", "#9fb5ff"), ("Mana", "마나", "#7f9fff"))
RF_COL = "#e8794f"


_DEGEN_SRC: list[dict] = []  # 지금 캐릭터의 지속 피해 출처 (PoB es_summary degenSources)


def set_degen_sources(src: list[dict] | None) -> None:
    global _DEGEN_SRC
    _DEGEN_SRC = list(src or [])


def _src_ko(e: dict) -> str:
    name = e.get("name") or ""
    try:
        if e.get("kind") == "skill":
            import skillnames

            return skillnames.ko(name) or name
        if e.get("kind") == "item":
            import ko2en

            return ko2en.name_ko(name) or name
    except Exception:  # noqa: BLE001
        return name
    if e.get("kind") == "tree":
        return "패시브"
    return name


def degen_label() -> str:
    """지속 피해 이름: '정의의 화염', '정의의 화염·피의 격노' … 모르면 '지속 피해'."""
    names = []
    for e in _DEGEN_SRC:
        n = _src_ko(e)
        if n and n not in names:
            names.append(n)
    if not names:
        return "지속 피해"
    return "·".join(names[:2]) + (" 등" if len(names) > 2 else "")


def _ro(word: str) -> str:
    """조사 '로/으로' (받침 없거나 ㄹ 받침이면 '로')."""
    ch = word[-1:] if word else ""
    if "가" <= ch <= "힣":
        jong = (ord(ch) - 0xAC00) % 28
        return "로" if jong in (0, 8) else "으로"
    return "로"


def _degen_skill() -> str:
    """지속 피해를 주는 스킬 이름 (껐다 켜는 것들: 정의의 화염 · 피의 격노 …). 없으면 빈 문자열."""
    names = []
    for e in _DEGEN_SRC:
        if e.get("kind") == "skill":
            n = _src_ko(e)
            if n and n not in names:
                names.append(n)
    return "·".join(names[:2])


def has_degen(*stats: dict) -> bool:
    return any((s or {}).get("TotalBuildDegen") or (s or {}).get("LifeDegen") for s in stats)


def net_regen(st: dict, pool: str) -> float | None:
    """순 회복(초당). PoB 는 지속 피해가 없으면 Net* 를 안 만들어서 그땐 재생 값 그대로."""
    v = st.get(f"Net{pool}Regen")
    return v if v is not None else st.get(f"{pool}RegenRecovery")


def degen_pools(*stats: dict) -> list[str]:
    """지속 피해를 실제로 받는 쪽 (중요한 순). 보호막 재생이 있으면 보호막 먼저."""
    out = []
    es = any(((s or {}).get("EnergyShieldRegenRecovery") or 0) > 0 for s in stats)
    if es:
        out.append("EnergyShield")
    # 생명력: 보호막 쪽이 아니면 다 받고, 보호막 쪽이어도 뚫고 들어오는 몫이 있으면
    if not es or any((net_regen(s or {}, "Life") or 0) < ((s or {}).get("LifeRegenRecovery") or 0) - 0.5 for s in stats):
        out.append("Life")
    if any((net_regen(s or {}, "Mana") or 0) < ((s or {}).get("ManaRegenRecovery") or 0) - 0.5 for s in stats):
        out.append("Mana")  # 마음의 지배 등으로 마나가 일부 받음
    return out


def _pool(p: str) -> tuple[str, str]:
    return next((nm, c) for k, nm, c in POOLS if k == p)


def _max_key(p: str) -> str:
    return "Life" if p == "Life" else "EnergyShield" if p == "EnergyShield" else "Mana"


def rf_lines(base: dict, new: dict) -> list[str]:
    """비교 창용 지속 피해(정의의 화염 · 피의 격노 등) 카드 (여러 줄 HTML). 지속 피해가 없으면 빈 목록."""
    if not base or not new or not has_degen(base, new):
        return []
    out = []
    da, db = base.get("TotalBuildDegen") or 0, new.get("TotalBuildDegen") or 0
    dcol = NEG if db > da + 0.05 else POS if db < da - 0.05 else DIM
    lab = degen_label()
    what = "스스로 받는 지속 피해" if lab == "지속 피해" else f"{lab}{_ro(lab)} 받는 피해"
    out.append(f"<span style='color:{RF_COL}; font-weight:bold'>{what}</span> {da:,.1f} → "
               f"<b style='color:{dcol}'>{db:,.1f}</b>/초")
    warns = []
    for i, p in enumerate(degen_pools(base, new)):
        nm, pc = _pool(p)
        a, b = net_regen(base, p), net_regen(new, p)
        if a is None or b is None:
            continue
        d = b - a
        col = POS if d > 0.05 else NEG if d < -0.05 else DIM
        size = "font-size:12.5pt; " if i == 0 else ""
        mx_a, mx_b = base.get(_max_key(p)) or 0, new.get(_max_key(p)) or 0
        share = ""
        if mx_a > 0 and mx_b > 0:
            share = f" <span style='color:{DIM}; font-size:10pt'>({nm}의 {a / mx_a * 100:.1f}% → {b / mx_b * 100:.1f}%)</span>"
        out.append(f"&nbsp;&nbsp;<span style='color:{pc}'>순 {nm} 회복</span> {a:+,.1f} → "
                   f"<b style='{size}color:{col}'>{b:+,.1f}</b>/초 "
                   f"<span style='color:{col}'>({d:+,.1f})</span>{share}")
        if b < 0:
            warns.append(nm)
    if warns:
        sk = _degen_skill()
        tail = f"{sk} 켜두면 계속 깎여요" if sk else "계속 깎여요"
        out.append(f"&nbsp;&nbsp;<b style='color:{NEG}'>⚠ 순 {'·'.join(warns)} 회복이 마이너스예요 — {tail}</b>")
    return out


def regen_cell(base: dict, new: dict) -> str:
    """생명력 재생 변화 한 칸. RF 등 지속 피해가 있으면 그걸 받는 쪽의 '순 회복' 기준 (음수면 경고)."""
    if not base or not new:
        return ""
    if has_degen(base, new):
        pools = degen_pools(base, new) or ["Life"]
        p = pools[0]
        nm, _ = _pool(p)
        a, b = net_regen(base, p), net_regen(new, p)
        if a is None or b is None or abs(b - a) < 1:
            return ""
        col = POS if b > a else NEG
        warn = f" <b style='color:{NEG}'>⚠ 마이너스</b>" if b < 0 <= a else ""
        return (f"<span style='color:{DIM}'>순 {nm} 회복</span> {a:,.0f} → "
                f"<b style='color:{col}'>{b:,.0f}</b>/초{warn}")
    a, b = base.get("LifeRegenRecovery"), new.get("LifeRegenRecovery")
    if a is None or b is None or abs(b - a) < 1:
        return ""
    col = POS if b > a else NEG
    return f"<span style='color:{DIM}'>체젠</span> <b style='color:{col}'>{b - a:+,.0f}</b>/초"


def maxhit_html(base: dict, new: dict, prefix: str = "최대 피격") -> str:
    """'최대 피격  물리 +2.0%  화염 -1.1% …  · 체젠 -42/초' 한 덩어리 (변화 없으면 빈 문자열)."""
    cells = maxhit_cells(base, new)
    rg = regen_cell(base, new)
    out = f"<span style='color:{DIM}'>{prefix}</span>&nbsp; " + " &nbsp;".join(cells) if cells else ""
    if rg:
        out = f"{out} &nbsp;·&nbsp; {rg}" if out else rg
    return out
