"""게임에서 Ctrl+C 한 아이템 텍스트 해석 + 필터 탭 판정(O / △ / X).

영문/한글 클라이언트 모두 지원: 옵션 DB 의 영문(en)·한글(ko) 템플릿 둘 다로 줄을 맞춘다.
템플릿의 '#' 자리가 수치. 대표값은 옵션의 metric (평균 비교 'avg2' / 첫 수치 'first').
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from data import ModDB, fmt_num, tier_for_value

# 아이템 텍스트의 'Item Class:' 값 → 옵션 DB 장비 종류 id
CLASS_NAMES = {
    "Helmets": "Helmet", "Body Armours": "Body Armour", "Gloves": "Gloves", "Boots": "Boots",
    "Shields": "Shield", "Amulets": "Amulet", "Rings": "Ring", "Belts": "Belt", "Quivers": "Quiver",
    "One Hand Swords": "One Hand Sword", "Thrusting One Hand Swords": "Thrusting One Hand Sword",
    "One Hand Axes": "One Hand Axe", "One Hand Maces": "One Hand Mace", "Sceptres": "Sceptre",
    "Claws": "Claw", "Daggers": "Dagger", "Rune Daggers": "Rune Dagger", "Wands": "Wand",
    "Two Hand Swords": "Two Hand Sword", "Two Hand Axes": "Two Hand Axe", "Two Hand Maces": "Two Hand Mace",
    "Bows": "Bow", "Staves": "Staff", "Warstaves": "Warstaff",
    # 한글 클라이언트
    "투구": "Helmet", "갑옷": "Body Armour", "장갑": "Gloves", "장화": "Boots", "방패": "Shield",
    "목걸이": "Amulet", "반지": "Ring", "허리띠": "Belt", "화살통": "Quiver",
    "한손 검": "One Hand Sword", "날카로운 한손 검": "Thrusting One Hand Sword", "한손 도끼": "One Hand Axe",
    "한손 철퇴": "One Hand Mace", "셉터": "Sceptre", "클로": "Claw", "단검": "Dagger", "룬 단검": "Rune Dagger",
    "마법봉": "Wand", "양손 검": "Two Hand Sword", "양손 도끼": "Two Hand Axe", "양손 철퇴": "Two Hand Mace",
    "활": "Bow", "지팡이": "Staff", "전쟁지팡이": "Warstaff", "전쟁 지팡이": "Warstaff",
}

SEP = "--------"
NUM = r"(-?\d+(?:\.\d+)?)"
# 고급 복사(Ctrl+Alt+C)의 '35(30-40)' 범위 표기 제거
ADV_RANGE_RE = re.compile(r"\(\s*-?\d+(?:\.\d+)?\s*-\s*-?\d+(?:\.\d+)?\s*\)")
TAG_RE = re.compile(r"\s*\(([^()\d]+)\)\s*$")
# 판정에 포함하는 꼬리표: 제작/분열 옵션은 접두/접미 취급. implicit, enchant 등은 제외.
COUNT_TAGS = {"crafted", "fractured", "제작", "분열", "제작됨", "분열됨"}


@dataclass
class ParsedItem:
    text: str
    lang: str  # "en" | "ko"
    class_label: str
    slot: str | None
    rarity: str
    name: str
    base: str
    mod_lines: list[str] = field(default_factory=list)


def parse_item(text: str) -> ParsedItem | None:
    if not text or SEP not in text:
        return None
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n")]
    if not lines or ":" not in lines[0]:
        return None
    head, _, cls = lines[0].partition(":")
    head, cls = head.strip(), cls.strip()
    if head not in ("Item Class", "아이템 종류"):
        return None
    lang = "ko" if head == "아이템 종류" else "en"
    rarity = ""
    if len(lines) > 1 and ":" in lines[1]:
        rarity = lines[1].partition(":")[2].strip()
    # 이름/베이스: 첫 구분선 전까지의 나머지 줄
    names = []
    for ln in lines[2:]:
        if ln == SEP:
            break
        names.append(ln)
    name = names[0] if names else ""
    base = names[1] if len(names) > 1 else name
    from itemmodel import parse as parse_model

    model = parse_model(text)
    # 필터 판정은 접두/접미 옵션 대상 → implicit·enchant 제외 (제작·분열은 포함)
    mods = [m.text for m in model.mods if m.kind in ("explicit", "crafted", "fractured")] if model else []
    return ParsedItem(text, lang, cls, CLASS_NAMES.get(cls), rarity, name, base, mods)


_rx_cache: dict[tuple[str, str], list[re.Pattern]] = {}


def _patterns(entry: dict, lang: str) -> list[re.Pattern]:
    k = (entry["key"], lang)
    if k not in _rx_cache:
        tpl = entry[lang] if entry.get(lang) else entry["en"]
        pats = []
        for part in tpl.split(" / "):
            part = re.sub(r"\s+", " ", part.strip())
            rx = re.escape(part).replace(r"\#", NUM).replace("#", NUM)
            pats.append(re.compile(rf"^{rx}$", re.IGNORECASE))
        _rx_cache[k] = pats
    return _rx_cache[k]


def mod_value(entry: dict, item: ParsedItem) -> float | None:
    """아이템에서 해당 옵션의 대표 수치. 없으면 None. 여러 줄 옵션은 모든 줄이 있어야 인정."""
    pats = _patterns(entry, item.lang)
    first_vals: list[float] | None = None
    for i, rx in enumerate(pats):
        found = None
        for ln in item.mod_lines:
            m = rx.match(ln)
            if m:
                found = [float(x) for x in m.groups()]
                break
        if found is None:
            return None
        if i == 0:
            first_vals = found
    if first_vals is None:
        return None
    if not first_vals:
        return 1.0  # 수치 없는 옵션 (예: 'Cannot be Frozen') — 있으면 1
    if entry.get("metric") == "avg2" and len(first_vals) >= 2:
        return (first_vals[0] + first_vals[1]) / 2
    return first_vals[0]


@dataclass
class OptionResult:
    key: str
    text: str
    want: float
    got: float | None
    verdict: str  # "O" | "△" | "X"
    want_tier: int | None
    got_tier: int | None


@dataclass
class TabResult:
    tab_name: str
    options: list[OptionResult]

    @property
    def counts(self) -> dict[str, int]:
        c = {"O": 0, "△": 0, "X": 0}
        for o in self.options:
            c[o.verdict] += 1
        return c

    @property
    def verdict(self) -> str:
        """탭 전체: 모두 O → O, X 없이 △ 섞임 → △, 하나라도 X → X."""
        c = self.counts
        if not self.options:
            return "X"
        if c["X"]:
            return "X"
        return "△" if c["△"] else "O"


def check_tab(db: ModDB, tab: dict, item: ParsedItem) -> TabResult:
    out = []
    for o in tab.get("options", []):
        e = db.get(o["key"])
        if not e:
            continue
        want = float(o["value"])
        got = mod_value(e, item)
        if got is None:
            v = "X"
        elif got + 1e-9 >= want:
            v = "O"
        else:
            v = "△"
        wt = tier_for_value(e, want)
        gt = tier_for_value(e, got) if got is not None else None
        out.append(OptionResult(o["key"], e["ko"], want, got, v,
                                wt["t"] if wt else None, gt["t"] if gt else None))
    return TabResult(tab.get("name", ""), out)


def check_item(db: ModDB, tabs: list[dict], item: ParsedItem) -> list[TabResult]:
    if not item.slot:
        return []
    return [check_tab(db, t, item) for t in tabs if t.get("slot") == item.slot and t.get("options")]


def fmt_val(entry_metric: str, v: float | None) -> str:
    if v is None:
        return "—"
    return ("평균 " if entry_metric == "avg2" else "") + fmt_num(round(v, 2))
