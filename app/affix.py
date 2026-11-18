"""옵션 줄이 접두(prefix)인지 접미(suffix)인지 — 옵션 DB(mods_ko.json)의 한글·영문 문장 골격으로 판별.

일반 Ctrl+C 텍스트에는 접두/접미 표시가 없어서(고급 복사 Ctrl+Alt+C 에만 있음) 문장으로 찾는다.
장비 종류(slot)를 알면 그 종류의 옵션부터 보고, 모르거나 없으면 전체에서 찾는다.
둘 다 될 수 있는 문장이면 "" (모름).
"""
from __future__ import annotations

import re

from itemmodel import skeleton

KO = {"prefix": "접두", "suffix": "접미"}
ORDER = {"prefix": 0, "suffix": 1, "": 2}
NO_DB = ("Jewel", "주얼", "Flask", "플라스크", "Map", "지도", "Tincture", "팅크", "Charm", "부적")

_idx: dict[str, dict[str, set[str]]] | None = None  # 골격 → {slot: {gen}}


def _index() -> dict[str, dict[str, set[str]]]:
    global _idx
    if _idx is None:
        _idx = {}
        try:
            from data import ModDB

            db = ModDB()
            for slot, lst in (*db.mods.items(), *db.crafted.items()):
                for e in lst:
                    gen = e.get("gen")
                    if gen not in KO:
                        continue
                    for lang in ("ko", "en"):
                        tpl = e.get(lang) or ""
                        for part in tpl.split(" / "):
                            sk = skeleton(part)
                            if sk:
                                _idx.setdefault(sk, {}).setdefault(slot, set()).add(gen)
        except Exception:  # noqa: BLE001
            pass
    return _idx


def _pick(gens: set[str]) -> str:
    return next(iter(gens)) if len(gens) == 1 else ""


def affix_of(text: str, slot: str | None = None) -> str:
    """'prefix' / 'suffix' / '' (모름). 여러 줄 옵션은 줄마다 보고 한쪽으로 정해지면 그쪽."""
    idx = _index()
    found: set[str] = set()
    for ln in text.split("\n"):
        by_slot = idx.get(skeleton(ln))
        if not by_slot:
            continue
        if slot and slot in by_slot:
            g = _pick(by_slot[slot])
        else:
            g = _pick(set().union(*by_slot.values()))
            if not g:  # 장비 종류마다 다르면 더 많은 종류에서 쓰는 쪽 (2배 이상 차이 날 때만)
                n = {k: sum(k in s for s in by_slot.values()) for k in KO}
                a, b = sorted(KO, key=lambda k: -n[k])
                g = a if n[a] >= 2 * n[b] else ""
        if g:
            found.add(g)
    return _pick(found)


# PoB 슬롯 이름 → 옵션 DB 장비 종류 (무기·방패는 종류를 몰라서 None → 전체에서 찾음)
POB_SLOT = {"Helmet": "Helmet", "Body Armour": "Body Armour", "Gloves": "Gloves", "Boots": "Boots",
            "Amulet": "Amulet", "Ring 1": "Ring", "Ring 2": "Ring", "Belt": "Belt"}


def db_slot(pob_slot: str | None) -> str | None:
    return POB_SLOT.get((pob_slot or "").replace(" Swap", ""))


def no_db(pob_slot: str | None) -> bool:
    """주얼 · 심연 · 플라스크 칸 (옵션 DB 에 없어서 접두/접미를 따지지 않음)."""
    s = pob_slot or ""
    return "Jewel" in s or "Abyssal" in s or "Flask" in s


def group(kind: str, aff: str) -> int:
    """보여줄 순서: 인챈트 → 고정(implicit) → 접두 → 접미 → 그 밖."""
    if kind == "enchant":
        return 0
    if kind == "implicit":
        return 1
    return 2 + ORDER.get(aff or "", 2)


def sort_key(m) -> int:
    return group(m.kind, m.affix)


def of_line(ln: dict, slot: str | None) -> str:
    """PoB 엔진이 돌려준 옵션 줄 {line, kind, ...} 의 접두/접미 (일반 옵션만)."""
    if ln.get("kind") not in (None, "explicit"):
        return ""
    if ln.get("prefix") or ln.get("affix") == "prefix":
        return "prefix"
    if ln.get("suffix") or ln.get("affix") == "suffix":
        return "suffix"
    return affix_of(ln.get("line") or "", slot)


def badge(aff: str):
    """오른쪽에 붙는 '접두' / '접미' 이름표 (QLabel). 모르면 None."""
    if aff not in KO:
        return None
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    b = QLabel(KO[aff])
    b.setObjectName("BadgePrefix" if aff == "prefix" else "BadgeSuffix")
    b.setAlignment(Qt.AlignmentFlag.AlignCenter)
    b.setFixedWidth(40)
    # 창마다 QLabel 글자색을 덮어쓰는 스타일이 있어서 색을 직접 지정
    b.setStyleSheet("color: #8f9fff; background: #18183a; border: 1px solid #34346e; border-radius: 4px; font-size: 9pt;"
                    if aff == "prefix" else
                    "color: #c8a96a; background: #261f12; border: 1px solid #5a4a2c; border-radius: 4px; font-size: 9pt;")
    b.setToolTip("접두 옵션" if aff == "prefix" else "접미 옵션")
    return b


def html_badge(aff: str) -> str:
    """글(HTML) 안에 넣는 '접두' / '접미' 표시."""
    if aff not in KO:
        return ""
    col = "#8f9fff" if aff == "prefix" else "#c8a96a"
    return f"<span style='color:{col}; font-size:9pt'>{KO[aff]}</span>"


# ---------------------------------------------------------------- 하이브리드 옵션 (한 옵션 = 여러 줄)
_NUM = re.compile(r"\d+(?:\.\d+)?")
_RNG = re.compile(r"\((\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\)|(\d+(?:\.\d+)?)")
_hyb: dict[tuple[str, ...], list[tuple[str, str, list[list[list[tuple[float, float]]]]]]] | None = None


def _ranges(t: str) -> list[tuple[float, float]]:
    out = []
    for m in _RNG.finditer(t):
        if m.group(1):
            out.append((float(m.group(1)), float(m.group(2))))
        else:
            v = float(m.group(3))
            out.append((v, v))
    return out


def _hybrids():
    """골격 줄 묶음(순서대로) → [(slot, gen, 티어마다 [줄마다 [수치 범위]])]. 줄 순서가 바뀌어 나와도 찾게 순열까지."""
    global _hyb
    if _hyb is None:
        _hyb = {}
        try:
            from itertools import permutations

            from data import ModDB

            db = ModDB()
            for slot, lst in (*db.mods.items(), *db.crafted.items()):
                for e in lst:
                    gen = e.get("gen")
                    ko_parts = (e.get("ko") or "").split(" / ")
                    if gen not in KO or len(ko_parts) < 2 or len(ko_parts) > 3:
                        continue
                    tiers = []
                    for t in e.get("tiers") or []:
                        tp = (t.get("text") or "").split(" / ")
                        if len(tp) == len(ko_parts):
                            tiers.append([_ranges(x) for x in tp])
                    for lang in ("ko", "en"):
                        parts = (e.get(lang) or "").split(" / ")
                        if len(parts) != len(ko_parts):
                            continue
                        sks = [skeleton(p) for p in parts]
                        for order in permutations(range(len(sks))):
                            key = tuple(sks[i] for i in order)
                            _hyb.setdefault(key, []).append(
                                (slot, gen, [[tr[i] for i in order] for tr in tiers]))
        except Exception:  # noqa: BLE001
            pass
    return _hyb


def _fits(lines: list[str], tiers) -> bool:
    """줄 수치가 어느 한 티어 범위 안에 다 들어가면 True (촉매 · 퀄리티로 조금 넘는 건 봐줌)."""
    if not tiers:
        return True
    vals = [[float(x) for x in _NUM.findall(ln)] for ln in lines]
    for tr in tiers:
        ok = True
        for v, rg in zip(vals, tr):
            if len(v) != len(rg) or any(not (lo - 1e-6 <= x <= hi * 1.3 + 1e-6) for x, (lo, hi) in zip(v, rg)):
                ok = False
                break
        if ok:
            return True
    return False


def hybrid_spans(texts: list[str], slot: str | None) -> list[tuple[int, int, str]]:
    """이어진 줄들 중 한 옵션(하이브리드)으로 보이는 구간 → [(시작, 줄 수, gen)]."""
    hyb = _hybrids()
    out, i = [], 0
    while i < len(texts):
        hit = None
        for n in (3, 2):
            seg = texts[i:i + n]
            if len(seg) < n:
                continue
            cands = hyb.get(tuple(skeleton(t) for t in seg)) or []
            if slot and any(c[0] == slot for c in cands):
                cands = [c for c in cands if c[0] == slot]
            gens = {c[1] for c in cands if _fits(seg, c[2])}
            if gens:
                hit = (i, n, _pick(gens))
                break
        if hit:
            out.append(hit)
            i += hit[1]
        else:
            i += 1
    return out


def fill(model, slot: str | None) -> None:
    """ItemModel 의 일반·제작·분열 옵션 줄에 affix(접두/접미)와 grp(한 옵션 묶음)를 채운다.
    고급 복사는 머리줄에 이미 둘 다 있음 → 그대로."""
    cls = (model.head[0] if model.head else "").partition(":")[2]
    if not slot and any(w in cls for w in NO_DB):
        return  # 주얼 · 플라스크 · 지도 등은 옵션 DB 에 없음 → 문장으로 짐작하지 않음
    if not any(m.grp for m in model.mods):
        nxt = 1000
        run: list = []  # 이어진 같은 종류 일반 옵션 줄

        def flush():
            nonlocal nxt
            for s, n, gen in hybrid_spans([m.text for m in run], slot):
                nxt += 1
                for m in run[s:s + n]:
                    m.grp = nxt
                    if gen and not m.affix:
                        m.affix = gen
            run.clear()

        for m in model.mods:
            if m.kind in ("explicit", "crafted", "fractured") and "\n" not in m.text:
                if run and run[-1].kind != m.kind:
                    flush()
                run.append(m)
            else:
                flush()
        flush()
    for m in model.mods:
        if m.kind in ("explicit", "crafted", "fractured") and not m.affix:
            m.affix = affix_of(m.text, slot)
    # 한 묶음은 접두/접미 하나 (줄마다 짐작이 갈리면 정해진 쪽으로)
    for g in {m.grp for m in model.mods} - {0}:
        ms = [m for m in model.mods if m.grp == g]
        affs = {m.affix for m in ms if m.affix}
        if len(affs) == 1:
            a = affs.pop()
            for m in ms:
                m.affix = a


def annotate(lines: list[dict], pob_slot: str | None) -> list[tuple[int, str]]:
    """PoB 엔진 옵션 줄 목록 → 줄마다 (묶음 번호, 접두/접미). 하이브리드 줄들은 같은 번호 · 같은 접두/접미.
    주얼 · 심연 · 플라스크 칸이면 전부 (0, "")."""
    if no_db(pob_slot):
        return [(0, "")] * len(lines)
    slot = db_slot(pob_slot)
    gid, gens = _line_groups(lines, slot)
    out = []
    for ln, g in zip(lines, gid):
        a = of_line(ln, slot)
        if g and gens.get(g):
            a = gens[g]
        out.append((g, a))
    # 묶음 안에서 접두/접미가 갈리면 정해진 쪽으로 통일
    for g in set(gid) - {0}:
        affs = {a for (gg, a) in out if gg == g and a}
        if len(affs) == 1:
            a = affs.pop()
            out = [(gg, a if gg == g else aa) for (gg, aa) in out]
    return out


def ordered(lines: list[dict], pob_slot: str | None) -> list[tuple[dict, int, str]]:
    """보여줄 순서로 정렬: [(줄, 묶음 번호, 접두/접미)] — 인챈트 → 고정 → 접두 → 접미, 묶음은 붙여서."""
    ann = annotate(lines, pob_slot)
    rows = [(ln, g, a) for ln, (g, a) in zip(lines, ann)]
    return sorted(rows, key=lambda r: group(r[0].get("kind") or "explicit", r[2]))


def _line_groups(lines: list[dict], slot: str | None) -> tuple[list[int], dict[int, str]]:
    gid = [0] * len(lines)
    gens: dict[int, str] = {}
    nxt = 0
    i = 0
    while i < len(lines):
        if (lines[i].get("kind") or "explicit") != "explicit":
            i += 1
            continue
        j = i
        while j < len(lines) and (lines[j].get("kind") or "explicit") == "explicit" \
                and bool(lines[j].get("crafted")) == bool(lines[i].get("crafted")):
            j += 1
        for s, n, gen in hybrid_spans([ln.get("line") or "" for ln in lines[i:j]], slot):
            nxt += 1
            gens[nxt] = gen
            for k in range(i + s, i + s + n):
                gid[k] = nxt
        i = j
    return gid, gens
