"""'왜 이렇게 바뀌나' 설명: PoB 엔진 es_explain_item 결과(옵션 줄마다 기여도)를 글로 만든다.

결과 형태: {slot, base, new, old_name, new_lines: [{line, kind, d: {FullDPS, TotalEHP, Life, ...}}], old_lines: [...]}
 - new_lines 의 d: 새 아이템에서 이 줄이 주는 양 (+면 이득)
 - old_lines 의 d: 지금 장비에서 이 줄이 주는 양 → 바꾸면 잃음 (부호를 뒤집어 표시)
"""
from __future__ import annotations

import html

from statfmt import DIM, NEG, POS

KIND_KO = {"enchant": "인챈트", "implicit": "implicit"}


def _ko(line: str) -> str:
    try:
        import ko2en

        return ko2en.passive_ko(line)
    except Exception:  # noqa: BLE001
        return line


def _hint(line: str, dps: float) -> str:
    """흔히 헷갈리는 경우 한 줄 설명."""
    low = line.lower()
    if abs(dps) < 1e-9:
        return ""
    if "maximum life" in low:
        return "최대 생명력에 비례하는 피해(정의의 화염 등)가 같이 바뀜"
    if "maximum mana" in low:
        return "최대 마나에 비례하는 피해가 같이 바뀜"
    if "energy shield" in low:
        return "에너지 보호막에 비례하는 피해(정의의 화염 등)가 같이 바뀜"
    if "strength" in low or "dexterity" in low or "intelligence" in low or "attributes" in low:
        return "능력치에 따른 피해·요구치가 바뀜"
    if "resistance" in low:
        return "저항(초과분)에 따라 피해가 바뀌는 효과가 있음"
    return ""


def _rows(res: dict, dk: str) -> list[dict]:
    """[{side: 'new'|'old', text, dps%, ehp%, life, hint}] — 차이가 있는 줄만."""
    base = res.get("base") or {}
    b_dps, b_ehp = base.get(dk) or 0.0, base.get("TotalEHP") or 0.0
    out = []
    for side, sign in (("new", 1), ("old", -1)):
        for ln in res.get(f"{side}_lines") or []:
            d = ln.get("d") or {}
            dps = sign * (d.get(dk) or 0.0)
            ehp = sign * (d.get("TotalEHP") or 0.0)
            life = sign * (d.get("Life") or 0.0)
            p_dps = dps / b_dps * 100 if b_dps and b_dps < 1e299 else 0.0
            p_ehp = ehp / b_ehp * 100 if b_ehp and b_ehp < 1e299 else 0.0
            if abs(p_dps) < 0.05 and abs(p_ehp) < 0.05:
                continue
            out.append({"side": side, "text": _ko(ln.get("line") or ""), "en": ln.get("line") or "",
                        "dps": p_dps, "ehp": p_ehp, "life": life, "hint": _hint(ln.get("line") or "", dps)})
    return out


def _total(res: dict, dk: str, key: str) -> float:
    a, b = (res.get("base") or {}).get(key) or 0.0, (res.get("new") or {}).get(key) or 0.0
    return (b - a) / a * 100 if a and a < 1e299 and b < 1e299 else 0.0


def _pc(v: float) -> str:
    col = POS if v > 0.05 else NEG if v < -0.05 else DIM
    return f"<b style='color:{col}'>{v:+.1f}%</b>"


def summary_html(results: list[tuple[str, dict]], dk: str) -> str:
    """마우스를 올렸을 때 보이는 짧은 요약: 슬롯마다 DPS / EHP 를 가장 크게 움직인 줄 2개씩."""
    blocks = []
    for label, res in results:
        rows = _rows(res, dk)
        lines = [f"<b style='color:#c8a96a'>{html.escape(label)}</b>"]
        for key, name in (("dps", "DPS"), ("ehp", "EHP")):
            top = sorted((r for r in rows if abs(r[key]) >= 0.05), key=lambda r: -abs(r[key]))[:2]
            if not top:
                continue
            why = " · ".join(
                f"{'' if r['side'] == 'new' else '잃음 '}{html.escape(r['text'])} {_pc(r[key])}" for r in top)
            lines.append(f"{name} {_pc(_total(res, dk, dk if key == 'dps' else 'TotalEHP'))}: {why}")
            hint = next((r["hint"] for r in top if key == "dps" and r["hint"]), "")
            if hint:
                lines.append(f"<span style='color:{DIM}'>&nbsp;&nbsp;→ {html.escape(hint)}</span>")
        if len(lines) == 1:
            lines.append(f"<span style='color:{DIM}'>옵션 줄 하나하나로는 차이가 거의 없음</span>")
        blocks.append("<br>".join(lines))
    return "<br><br>".join(blocks) + f"<br><br><span style='color:{DIM}'>클릭하면 옵션 줄마다 자세히</span>"


def detail_html(results: list[tuple[str, dict]], dk: str) -> str:
    """클릭했을 때: 옵션 줄마다 DPS / EHP / 생명력 기여도 표."""
    dname = "Full DPS" if dk == "FullDPS" else "DPS"
    out = [f"<span style='color:{DIM}; font-size:10pt'>옵션을 한 줄씩 빼고 다시 계산한 값 "
           f"(+ 는 이득, − 는 손해 · 지금 상태 대비 %)</span>"]
    for label, res in results:
        rows = _rows(res, dk)
        t = [f"<tr><td colspan='4' style='color:#c8a96a; padding-top:6px'><b>{html.escape(label)}</b></td></tr>",
             f"<tr style='color:{DIM}'><td></td><td align='right'>&nbsp;{dname}&nbsp;</td>"
             f"<td align='right'>&nbsp;EHP&nbsp;</td><td align='right'>&nbsp;생명력</td></tr>"]
        for side, title in (("new", "새 아이템이 주는 것"), ("old", f"빠지는 것 ({res.get('old_name') or '지금 장비'})")):
            rs = [r for r in rows if r["side"] == side]
            if not rs:
                continue
            t.append(f"<tr><td colspan='4' style='color:{DIM}'>{html.escape(title)}</td></tr>")
            for r in sorted(rs, key=lambda r: -abs(r["dps"]) - abs(r["ehp"]) * 0.01):
                life = f"{r['life']:+.0f}" if abs(r["life"]) >= 0.5 else ""
                t.append(f"<tr><td>&nbsp;&nbsp;{html.escape(r['text'])}</td><td align='right'>{_pc(r['dps'])}</td>"
                         f"<td align='right'>{_pc(r['ehp'])}</td><td align='right'>{life}</td></tr>")
                if r["hint"]:
                    t.append(f"<tr><td colspan='4' style='color:{DIM}; font-size:9.5pt'>&nbsp;&nbsp;&nbsp;&nbsp;→ "
                             f"{html.escape(r['hint'])}</td></tr>")
        # 줄마다 합과 전체 변화의 차이 = 베이스(방어도 등)·옵션끼리 겹치는 효과
        s_dps = sum(r["dps"] for r in rows)
        s_ehp = sum(r["ehp"] for r in rows)
        tot_dps, tot_ehp = _total(res, dk, dk), _total(res, dk, "TotalEHP")
        rest_dps, rest_ehp = tot_dps - s_dps, tot_ehp - s_ehp
        if abs(rest_dps) >= 0.1 or abs(rest_ehp) >= 0.1:
            t.append(f"<tr><td style='color:{DIM}'>&nbsp;&nbsp;그 밖 (베이스 방어도·옵션끼리 겹치는 효과)</td>"
                     f"<td align='right'>{_pc(rest_dps)}</td><td align='right'>{_pc(rest_ehp)}</td><td></td></tr>")
        t.append(f"<tr><td><b>합계</b></td><td align='right'>{_pc(tot_dps)}</td>"
                 f"<td align='right'>{_pc(tot_ehp)}</td><td></td></tr>")
        out.append("<table cellspacing='0' cellpadding='1' width='100%'>" + "".join(t) + "</table>")
    return "".join(out)
