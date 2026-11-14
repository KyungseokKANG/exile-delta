"""작열의 총주교 / 세계 포식자 / 바알(타락) implicit 목록 — 설치된 PoB 의 데이터 파일에서 읽는다.

- src/Data/ModEldritch.lua  : type "Exarch" / "Eater" (티어 1~6, '고유 적/최종 보스 접근' 변형 포함)
- src/Data/ModCorrupted.lua : type "Corrupted"
문장이 PoB 가 해석하는 영문 그대로라 계산이 정확하다. 장비 종류에 붙을 수 있는지는 weightKey/weightVal
(앞에서부터 아이템 태그와 처음 맞는 키의 가중치 > 0) 로 판단.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

LINE_RE = re.compile(
    r'^\s*\["(?P<id>[^"]+)"\] = \{ type = "(?P<type>\w+)", affix = "[^"]*", (?P<texts>(?:"(?:[^"\\]|\\.)*", )+)'
    r'statOrder = \{[^}]*\}, level = (?P<level>\d+), group = "(?P<group>[^"]*)", '
    r'weightKey = \{ (?P<keys>[^}]*)\}, weightVal = \{ (?P<vals>[^}]*)\}')
STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
TYPE_SUB = {"Exarch": "exarch", "Eater": "eater", "Corrupted": "corrupted"}
SUB_NAME = {"exarch": "작열의 총주교", "eater": "세계 포식자", "corrupted": "바알 (타락)"}
ELDRITCH_RANK = {1: "하급", 2: "상급", 3: "우수한", 4: "특출난", 5: "정교한", 6: "완벽한"}  # 게임 한글 표기
RANGE_RE = re.compile(r"\((-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)\)")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass
class Tier:
    id: str
    level: int
    texts: list[str]   # 영문 (범위 포함 가능)
    label: str = ""


@dataclass
class Group:
    sub: str           # exarch / eater / corrupted
    group: str
    tiers: list[Tier] = field(default_factory=list)
    title_en: str = ""
    title_ko: str = ""


_cache: dict[str, list[tuple[str, Tier, list[str], list[int]]]] = {}


def _load(src: Path) -> list[tuple[str, Tier, list[str], list[int]]]:
    key = str(src)
    if key in _cache:
        return _cache[key]
    out = []
    for fn in ("ModEldritch.lua", "ModCorrupted.lua"):
        p = src / "Data" / fn
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LINE_RE.match(line)
            if not m or m.group("type") not in TYPE_SUB:
                continue
            texts = [t.replace('\\"', '"') for t in STR_RE.findall(m.group("texts"))]
            keys = STR_RE.findall(m.group("keys"))
            vals = [int(float(v)) for v in re.findall(r"-?\d+(?:\.\d+)?", m.group("vals"))]
            out.append((TYPE_SUB[m.group("type")] + "|" + m.group("group"),
                        Tier(m.group("id"), int(m.group("level")), texts), keys, vals))
    _cache[key] = out
    return out


def _class_tags(item_class: str) -> set[str]:
    from data import resource_path

    try:
        d = json.loads(resource_path("data/ko_en.json").read_text(encoding="utf-8"))
        return set(d.get("class_tags", {}).get(item_class, [])) | {"default"}
    except Exception:  # noqa: BLE001
        return {"default"}


def _spawns(keys: list[str], vals: list[int], tags: set[str]) -> bool:
    for k, v in zip(keys, vals):
        if k in tags:
            return v > 0
    return False


def _template(text: str) -> str:
    return NUM_RE.sub("#", RANGE_RE.sub("#", text))


def groups_for(src: Path, item_class: str | None, lang: str = "ko") -> list[Group]:
    """이 장비 종류에 붙을 수 있는 총주교/포식자/바알 implicit 묶음 (티어 오름차순)."""
    if not item_class:
        return []
    tags = _class_tags(item_class)
    by: dict[str, Group] = {}
    for gkey, tier, keys, vals in _load(src):
        if not _spawns(keys, vals, tags):
            continue
        sub, grp = gkey.split("|", 1)
        g = by.get(gkey)
        if g is None:
            g = by[gkey] = Group(sub, grp)
        g.tiers.append(tier)
    import ko2en

    out = []
    for g in by.values():
        if g.sub == "corrupted":
            g.tiers.sort(key=lambda t: t.level)
            for i, t in enumerate(g.tiers, 1):
                t.label = f"{i}단계 · 요구 레벨 {t.level}"
        else:
            def rank(t):
                m = re.search(r"(\d+)$", t.id)
                return int(m.group(1)) if m else 0
            g.tiers.sort(key=rank)
            for t in g.tiers:
                r = rank(t)
                t.label = f"{ELDRITCH_RANK.get(r, r)} ({r}등급)"
        g.title_en = " / ".join(_template(x) for x in g.tiers[-1].texts)
        if lang == "ko":
            top = [RANGE_RE.sub(lambda m: m.group(2), x) for x in g.tiers[-1].texts]
            ko = [ko2en.en_to_ko(x) for x in top]
            g.title_ko = " / ".join(NUM_RE.sub("#", k) if k else _template(e) for k, e in zip(ko, top))
        else:
            g.title_ko = g.title_en
        out.append(g)
    order = {"exarch": 0, "eater": 1, "corrupted": 2}
    out.sort(key=lambda g: (order.get(g.sub, 9), g.title_ko))
    return out


def tier_pairs(tier: Tier, lang: str) -> list[tuple[str, str]]:
    """티어의 최고 굴림 수치로 (표시 문장, 영문) 쌍. 한글 아이템이면 표시는 한글(변환 불가 시 영문)."""
    import ko2en

    out = []
    for t in tier.texts:
        en = RANGE_RE.sub(lambda m: m.group(2), t)
        out.append(((ko2en.en_to_ko(en) or en) if lang == "ko" else en, en))
    return out


def tier_lines(tier: Tier, lang: str) -> list[str]:
    return [shown for shown, _ in tier_pairs(tier, lang)]
