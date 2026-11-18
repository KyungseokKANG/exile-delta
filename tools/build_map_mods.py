"""지도 옵션 목록 (비선호 지도 체크용) → data/map_mods.json

RePoE mods(영문·한글)에서 지도에 붙는 접두/접미 옵션(일반 지도·17티어·메이븐 초대장 등)과
지도 고정 옵션 · 바알 타락 옵션을 모아
보상 줄(아이템 수량/희귀도/무리 규모 등)은 빼고 '위험 줄'만 남긴다. 티어끼리는 수치만 다르므로
수치를 '#' 로 바꾼 골격이 같으면 한 줄로 묶는다.

  python tools/build_map_mods.py [--refresh]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import dict_builder as db  # noqa: E402

TAGS = {"default", "low_tier_map", "mid_tier_map", "top_tier_map", "uber_tier_map",
        "has_uber_map_prefix", "has_uber_map_suffix", "maven_map", "primordial_map"}
REWARD = re.compile(r"found in|pack size|quantity of items|rarity of items|experience gain", re.I)
MARK = re.compile(r"\[([^\]|]+)\|([^\]]+)\]")
MARK1 = re.compile(r"\[([^\]|]+)\]")
RANGE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")
NUM = re.compile(r"[+-]?\d+(?:\.\d+)?")


def clean(s: str) -> str:
    return MARK1.sub(r"\1", MARK.sub(r"\2", s)).strip()


def skel(s: str) -> str:
    s = RANGE.sub("#", clean(s))
    s = NUM.sub("#", s)
    s = re.sub(r"[+-]#", "#", s)  # 앱 쪽 mapcheck.skel 과 똑같이 (부호 무시)
    return re.sub(r"\s+", " ", s).strip().lower()


SRANGE = re.compile(r"([+-]?)\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")


def nice(s: str) -> str:
    """'(20-29)' → '20~29', '-(12-9)' → '-9~-12', '(60-50)' → '50~60'."""
    def rep(m):
        sign, a, b = m.group(1), float(m.group(2)), float(m.group(3))
        lo, hi = sorted((a, b), key=abs)
        f = lambda v: f"{sign}{v:g}" if sign == "-" else (f"+{v:g}" if sign == "+" else f"{v:g}")
        return f"{f(lo)}~{f(hi)}"

    return SRANGE.sub(rep, clean(s))


TOK = re.compile(r"([+-]?)\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)|([+-]?)(\d+(?:\.\d+)?)")


def merged(texts: list[str]) -> str:
    """같은 옵션의 티어별 문장들 → 수치 자리마다 전체 범위. 예: '-(12-9)%', '-20%' → '-9~-20%'."""
    texts = [clean(t) for t in texts]
    toks = [list(TOK.finditer(t)) for t in texts]
    base = toks[0]
    if any(len(x) != len(base) for x in toks):
        return nice(texts[0])
    out, last = [], 0
    for i, m in enumerate(base):
        vals = []
        for x in toks:
            mm = x[i]
            if mm.group(2) is not None:
                vals += [abs(float(mm.group(2))), abs(float(mm.group(3)))]
            else:
                vals.append(abs(float(mm.group(5))))
        sign = m.group(1) if m.group(2) is not None else m.group(4)
        lo, hi = min(vals), max(vals)
        f = lambda v: f"{v:g}"
        if lo == hi:
            s = f"{sign}{f(lo)}"
        elif sign == "-":
            s = f"-{f(lo)}~-{f(hi)}"
        else:
            s = f"{sign}{f(lo)}~{f(hi)}"
        out.append(texts[0][last:m.start()] + s)
        last = m.end()
    out.append(texts[0][last:])
    return "".join(out)


def tier_of(tags: set[str]) -> str:
    if tags & {"uber_tier_map", "has_uber_map_prefix", "has_uber_map_suffix"}:
        return "t17"
    if tags & {"maven_map", "primordial_map"}:
        return "maven"
    return "map"


def kind_of(key: str, m: dict) -> str | None:
    """지도에 붙는 옵션이면 tier 이름, 아니면 None.
    접두/접미 → map/maven/t17, 지도 고정 옵션(지역에 환영의 거울 등장 등) → implicit,
    바알 오브 타락 옵션(바알 스킬 영혼 획득 방지 미적용 등) → corrupt."""
    if m.get("domain") != "area":
        return None
    tags = {w["tag"].strip() for w in m.get("spawn_weights", []) if w.get("weight", 0) > 0}
    g = m.get("generation_type")
    if g in ("prefix", "suffix"):
        return tier_of(tags) if tags & TAGS else None
    if g == "corrupted" and "default" in tags:
        return "corrupt"
    if g == "unique" and key.startswith("EverythingSomewhere") and "default" in tags:
        return "implicit"
    return None


def main() -> None:
    refresh = "--refresh" in sys.argv
    en = db.fetch("mods.min.json", refresh)
    ko = db.fetch("Korean/mods.min.json", refresh)
    out: dict[str, dict] = {}
    rank = {"map": 0, "maven": 1, "t17": 2, "implicit": 3, "corrupt": 4}
    for key, m in en.items():
        t = kind_of(key, m)
        if t is None:
            continue
        el = [x for x in (m.get("text") or "").split("\n") if x.strip()]
        kl = [x for x in ((ko.get(key) or {}).get("text") or "").split("\n") if x.strip()]
        if len(el) != len(kl):
            kl = [""] * len(el)
        for e, k in zip(el, kl):
            if REWARD.search(e):
                continue
            sk = skel(e)
            cur = out.get(sk)
            if cur is None:
                out[sk] = cur = {"key": sk, "ko_sk": skel(k) if k else "", "tiers": [], "_en": [], "_ko": []}
            if t not in cur["tiers"]:
                cur["tiers"].append(t)
            cur["_en"].append(e)
            cur["_ko"].append(k or e)
            if k and not cur["ko_sk"]:
                cur["ko_sk"] = skel(k)
    lines = []
    for v in out.values():
        v["en"], v["ko"] = merged(v.pop("_en")), merged(v.pop("_ko"))
        v["tiers"].sort(key=lambda x: rank[x])
        lines.append(v)
    lines.sort(key=lambda v: (rank[v["tiers"][0]], v["ko"]))
    p = ROOT / "data" / "map_mods.json"
    p.write_text(json.dumps({"lines": lines}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from collections import Counter
    print(f"map_mods.json: {len(lines)} lines", Counter(v["tiers"][0] for v in lines))


if __name__ == "__main__":
    main()
