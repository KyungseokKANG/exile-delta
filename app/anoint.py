"""목걸이 성유(Anoint) — 성유로 배정할 수 있는 패시브 목록 (PoB 트리 데이터의 recipe).

- 패시브 이름 · 효과 · 필요 성유 3개: src/TreeData/<최신 버전>/tree.lua 의 노드 중 recipe 가 있는 것
- 한글 이름: data/ko_en.json stats 의 '할당 X' ↔ 'Allocates X' (게임 거래소 옵션 문구)
- 한글 효과: ko2en.passive_ko · 성유 한글 이름: ko_en.json bases ('호박빛 성유' 등)
- 아이템 줄: 'Allocates <영문 이름>' (enchant) — PoB 가 그 패시브를 찍은 것으로 계산
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ANOINT_RE = re.compile(r"^\s*(?:Allocates\s+|할당\s+)(.+?)\s*$")
_VER_RE = re.compile(r"^(\d+)_(\d+)$")
_NODE_RE = re.compile(r"^\t\t\[(\d+)\] = \{\s*$")
_KEY_RE = re.compile(r'^\t\t\t\["(\w+)"\] = (.*?),?\s*$')
_STR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


@dataclass
class Anoint:
    en: str
    ko: str
    stats_en: list[str] = field(default_factory=list)
    stats_ko: list[str] = field(default_factory=list)
    oils_en: list[str] = field(default_factory=list)
    oils_ko: list[str] = field(default_factory=list)
    blighted: bool = False  # 성유로만 얻는 패시브 (트리엔 없음)

    @property
    def line_en(self) -> str:
        return f"Allocates {self.en}"

    @property
    def line_ko(self) -> str:
        return f"할당 {self.ko}"

    def search_text(self) -> str:
        return "\n".join([self.en, self.ko, *self.stats_en, *self.stats_ko, *self.oils_en, *self.oils_ko]).lower()


def _tree_file(src: Path) -> Path | None:
    td = Path(src) / "TreeData"
    best = None
    for d in td.iterdir() if td.is_dir() else []:
        m = _VER_RE.match(d.name)
        if m and (d / "tree.lua").exists():
            ver = (int(m.group(1)), int(m.group(2)))
            if best is None or ver > best[0]:
                best = (ver, d / "tree.lua")
    return best[1] if best else None


def _parse_tree(path: Path) -> list[dict]:
    """tree.lua 의 nodes 표에서 recipe 가 있는 노드 [{name, stats, recipe, blighted}]."""
    out, cur, key, buf = [], None, None, []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if _NODE_RE.match(line):
            cur, key = {}, None
            continue
        if cur is None:
            continue
        if key:  # 여러 줄 목록 ({ … }) 안
            if line.startswith("\t\t\t}"):
                cur[key] = [s.replace('\\"', '"') for s in buf]
                key, buf = None, []
            else:
                buf.extend(_STR_RE.findall(line))
            continue
        if line.startswith("\t\t}") or not line.startswith("\t\t"):  # 노드 끝 (또는 nodes 표 끝)
            if cur.get("recipe") and cur.get("name"):
                out.append(cur)
            cur = None
            continue
        m = _KEY_RE.match(line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if k in ("recipe", "stats") and v.startswith("{"):
            items = _STR_RE.findall(v)
            if v.rstrip(",").endswith("}"):
                cur[k] = items
            else:
                key, buf = k, items
        elif k == "name":
            s = _STR_RE.findall(v)
            cur["name"] = s[0].replace('\\"', '"') if s else ""
        elif k == "isBlighted":
            cur["blighted"] = v.startswith("true")
    return out


_cache: dict[str, list[Anoint]] = {}


def _ko_tables() -> tuple[dict[str, str], dict[str, str]]:
    from data import resource_path

    try:
        d = json.loads(resource_path("data/ko_en.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}, {}
    names = {}
    for ko, en in d.get("stats") or []:
        m, mk = ANOINT_RE.match(en or ""), ANOINT_RE.match(ko or "")
        if m and mk and en.startswith("Allocates"):
            names[m.group(1)] = mk.group(1)
    oils = {en: ko for ko, en in (d.get("bases") or {}).items() if isinstance(en, str) and en.endswith(" Oil")}
    return names, oils


def _oil_en(key: str) -> str:
    """'AmberOil' → 'Amber Oil'."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key)


def load(src: Path) -> list[Anoint]:
    """성유로 배정할 수 있는 패시브 전체 (한글 이름순). PoB 가 없으면 빈 목록."""
    key = str(src)
    if key in _cache:
        return _cache[key]
    path = _tree_file(Path(src))
    if path is None:
        return []
    import ko2en

    names, oils = _ko_tables()
    seen, out = set(), []
    for n in _parse_tree(path):
        if n["name"] in seen:
            continue
        seen.add(n["name"])
        oe = [_oil_en(o) for o in n["recipe"]]
        stats = [s for s in n.get("stats") or [] if s.strip()]
        out.append(Anoint(
            en=n["name"], ko=names.get(n["name"], n["name"]),
            stats_en=stats, stats_ko=[ko2en.passive_ko(s) for s in stats],
            oils_en=oe, oils_ko=[oils.get(o, o) for o in oe], blighted=bool(n.get("blighted"))))
    out.sort(key=lambda a: a.ko)
    _cache[key] = out
    return out


def find(src: Path, name: str) -> Anoint | None:
    """영문 또는 한글 패시브 이름 → Anoint."""
    name = name.strip()
    for a in load(src):
        if name in (a.en, a.ko):
            return a
    return None


def name_of(line: str) -> str | None:
    """'할당 X' / 'Allocates X' 줄 → 패시브 이름 (성유 줄이 아니면 None)."""
    m = ANOINT_RE.match(line or "")
    return m.group(1) if m else None
