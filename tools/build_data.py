"""RePoE(repoe-fork) 데이터를 받아 앱에서 쓰는 data/mods_ko.json 을 생성한다.

사용법:
    python tools/build_data.py            # 캐시 있으면 재사용
    python tools/build_data.py --refresh  # 새로 다운로드
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools" / ".cache"
OUT = ROOT / "data" / "mods_ko.json"
BASE_URL = "https://repoe-fork.github.io"

FILES = {
    "mods_en": "mods.min.json",
    "mods_ko": "Korean/mods.min.json",
    "bases_en": "base_items.min.json",
    "classes": "item_classes.min.json",
}

# (item_class, 한글명, 분류)
SLOTS = [
    ("Helmet", "투구", "방어구"),
    ("Body Armour", "갑옷", "방어구"),
    ("Gloves", "장갑", "방어구"),
    ("Boots", "장화", "방어구"),
    ("Shield", "방패", "방어구"),
    ("Amulet", "목걸이", "장신구"),
    ("Ring", "반지", "장신구"),
    ("Belt", "허리띠", "장신구"),
    ("Quiver", "화살통", "장신구"),
    ("One Hand Sword", "한손 검", "한손 무기"),
    ("Thrusting One Hand Sword", "찌르기 한손 검", "한손 무기"),
    ("One Hand Axe", "한손 도끼", "한손 무기"),
    ("One Hand Mace", "한손 철퇴", "한손 무기"),
    ("Sceptre", "셉터", "한손 무기"),
    ("Claw", "클로", "한손 무기"),
    ("Dagger", "단검", "한손 무기"),
    ("Rune Dagger", "룬 단검", "한손 무기"),
    ("Wand", "마법봉", "한손 무기"),
    ("Two Hand Sword", "양손 검", "양손 무기"),
    ("Two Hand Axe", "양손 도끼", "양손 무기"),
    ("Two Hand Mace", "양손 철퇴", "양손 무기"),
    ("Bow", "활", "양손 무기"),
    ("Staff", "지팡이", "양손 무기"),
    ("Warstaff", "전쟁 지팡이", "양손 무기"),
]

INFLUENCES = {
    "shaper": "쉐이퍼",
    "elder": "엘더",
    "crusader": "십자군",
    "basilisk": "사냥꾼",
    "eyrie": "대속자",
    "adjudicator": "전쟁군주",
}

RANGE_RE = re.compile(r"\(\s*-?\d+(?:\.\d+)?\s*[-~]\s*-?\d+(?:\.\d+)?\s*\)")
NUM_RE = re.compile(r"(?<![\w#.])-?\d+(?:\.\d+)?")


def fetch(name: str, refresh: bool) -> object:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / FILES[name].replace("/", "_")
    if refresh or not path.exists():
        url = f"{BASE_URL}/{FILES[name]}"
        print(f"download {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "exile-delta-data-builder"})
        with urllib.request.urlopen(req, timeout=120) as r:
            path.write_bytes(r.read())
    return json.loads(path.read_text(encoding="utf-8"))


def template(texts: list[str]) -> str:
    """여러 티어 문장에서 티어마다 달라지는 수치만 # 으로 바꾼다 (고정 숫자는 유지)."""
    base = texts[0]
    toks = [list(TOKEN_RE.finditer(t)) for t in texts]
    n = len(toks[0])
    parts, last = [], 0
    for i, mt in enumerate(toks[0]):
        fixed = mt.group(3) is not None and all(
            len(tk) == n and tk[i].group(3) == mt.group(3) for tk in toks
        )
        if len(texts) == 1:
            fixed = False
        parts.append(base[last:mt.start()])
        parts.append(mt.group(0) if fixed else "#")
        last = mt.end()
    parts.append(base[last:])
    t = "".join(parts)
    return " / ".join(s.strip() for s in t.splitlines() if s.strip())


def spawn_weight(mod: dict, tags: set[str]) -> int:
    for sw in mod["spawn_weights"]:
        if sw["tag"] in tags:
            return sw["weight"]
    return 0


TOKEN_RE = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*[-~]\s*(-?\d+(?:\.\d+)?)\s*\)|(?<![\w.])(-?\d+(?:\.\d+)?)")


def display_ranges(text: str) -> list[tuple[float, float]]:
    """게임에 표시되는 문장(영문)에서 수치 토큰을 순서대로 (lo, hi)로 뽑는다."""
    out = []
    for a, b, n in TOKEN_RE.findall(text):
        if n:
            out.append((float(n), float(n)))
        else:
            out.append((float(a), float(b)))
    return out


PAIR_RE = re.compile(r"(?:\([^)]*\)|\d+(?:\.\d+)?) to (?:\([^)]*\)|\d+(?:\.\d+)?)")


def metric_kind(en_text: str) -> str:
    """비교에 쓸 대표값 계산 방식. 'X to Y' 피해 범위는 평균, 그 외는 첫 수치."""
    return "avg2" if PAIR_RE.search(en_text.splitlines()[0]) else "first"


def metric(kind: str, values: list[float]) -> float:
    if not values:
        return 0.0
    if kind == "avg2" and len(values) >= 2:
        return (values[0] + values[1]) / 2
    return values[0]


def main() -> None:
    refresh = "--refresh" in sys.argv
    mods_en = fetch("mods_en", refresh)
    mods_ko = fetch("mods_ko", refresh)
    bases = fetch("bases_en", refresh)
    classes = fetch("classes", refresh)

    candidates = {
        mid: m
        for mid, m in mods_en.items()
        if m["domain"] == "item"
        and m["generation_type"] in ("prefix", "suffix")
        and not m.get("is_essence_only")
        and m["stats"]
    }
    print(f"candidate mods: {len(candidates)}")

    out_slots = []
    out_mods: dict[str, list] = {}

    for cls, ko_name, category in SLOTS:
        base_tags = [
            set(b["tags"])
            for b in bases.values()
            if b["item_class"] == cls and b.get("release_state") == "released" and b.get("domain") == "item"
        ]
        if not base_tags:
            print(f"skip {cls}: no bases")
            continue
        inf_tags = classes.get(cls, {}).get("influence_tags", [])

        # (influence, ladder key) -> list of mod ids
        ladders: dict[tuple[str, str], list[str]] = {}
        for mid, m in candidates.items():
            inf = ""
            ok = any(spawn_weight(m, t) > 0 for t in base_tags)
            if not ok:
                for it in inf_tags:
                    if any(spawn_weight(m, t | {it}) > 0 for t in base_tags):
                        inf = it.rsplit("_", 1)[-1]
                        ok = True
                        break
            if not ok:
                continue
            stat_ids = [s["id"] for s in m["stats"]]
            key = f"{m['type']}|{','.join(stat_ids)}|{m['generation_type']}"
            ladders.setdefault((inf, key), []).append(mid)

        entries = []
        for (inf, key), mids in ladders.items():
            mids.sort(key=lambda x: (candidates[x]["required_level"], x), reverse=True)
            top = candidates[mids[0]]
            kind = metric_kind(top["text"])
            tiers = []
            for i, mid in enumerate(mids, start=1):
                m = candidates[mid]
                ranges = display_ranges(m["text"].splitlines()[0])
                lo = metric(kind, [r[0] for r in ranges])
                hi = metric(kind, [r[1] for r in ranges])
                tiers.append({
                    "t": i,
                    "lv": m["required_level"],
                    "name": mods_ko.get(mid, {}).get("name") or m["name"],
                    "text": (mods_ko.get(mid, {}).get("text") or m["text"]).replace("\n", " / "),
                    "lo": min(lo, hi),
                    "hi": max(lo, hi),
                })
            ko_texts = [mods_ko.get(x, {}).get("text") or candidates[x]["text"] for x in mids]
            en_texts = [candidates[x]["text"] for x in mids]
            entries.append({
                "key": f"{cls}|{inf}|{key}",
                "gen": top["generation_type"],
                "inf": inf,
                "ko": template(ko_texts),
                "en": template(en_texts),
                "metric": kind,
                "decimals": 1 if any(t["lo"] != int(t["lo"]) or t["hi"] != int(t["hi"]) for t in tiers) else 0,
                "tiers": tiers,
            })
        entries.sort(key=lambda e: (e["inf"] != "", e["inf"], e["gen"], e["ko"]))
        out_mods[cls] = entries
        out_slots.append({"id": cls, "ko": ko_name, "en": cls, "category": category})
        print(f"{cls:28s} {len(entries):4d} options")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "built": date.today().isoformat(),
                "source": BASE_URL,
                "influences": INFLUENCES,
                "slots": out_slots,
                "mods": out_mods,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
