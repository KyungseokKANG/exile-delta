"""스킬 · 소환수 이름 한글 표시 (위쪽 '계산 기준 스킬' 줄, DPS 칸).

- 스킬 젬 이름: data/names_ko.json (RePoE 한글 젬 데이터)
- 소환수 이름: 아래 표 (게임 한글 옵션 문장에 나오는 공식 표기에서 뽑음. 예: '면죄의 파수꾼 지속시간 증가')
- 소환수가 쓰는 몬스터 스킬(예: Absolution Cascade)은 한글 자료가 없어서 영문 그대로
"""
from __future__ import annotations

MINIONS_KO = {
    "Sentinel of Absolution": "면죄의 파수꾼",
    "Sentinel of Dominance": "지배의 파수꾼",
    "Sentinel of Purity": "정화의 파수꾼",
    "Sentinel of Radiance": "광휘의 파수꾼",
    "Raised Zombie": "좀비",
    "Raging Spirit": "격노의 유령",
    "Summoned Skeleton": "해골",
    "Summoned Skeleton Soldier": "해골 병사",
    "Summoned Skeleton Warrior": "해골 전사",
    "Summoned Skeleton Archer": "궁수 해골",
    "Summoned Skeleton Caster": "마법사 해골",
    "Agony Crawler": "고통의 벌레",
    "Animated Guardian": "기동된 수호자",
    "Animated Weapon": "기동된 무기",
    "Carrion Golem": "부패 골렘",
    "Chaos Golem": "카오스 골렘",
    "Flame Golem": "화염 골렘",
    "Ice Golem": "얼음 골렘",
    "Lightning Golem": "번개 골렘",
    "Stone Golem": "돌 골렘",
    "Holy Relic": "신성한 유물",
    "Holy Armament": "신성한 병기",
    "Reaper": "수확자",
    "Clone": "분신",
    "Chilling Skitterbot": "냉각 원격 기폭 장치",
    "Shocking Skitterbot": "감전 원격 기폭 장치",
    "Scorching Skitterbot": "작열하는 원격 기폭 장치",
    "Living Lightning": "살아 있는 번개",
    "Summoned Phantasm": "환영",
    "Summoned Arbalist": "석궁병",
    "Void Spawn": "공허 유충",
}


def _names() -> dict:
    try:
        from pob import config_ko

        return config_ko._load_names()
    except Exception:  # noqa: BLE001
        return {}


def ko(en: str) -> str:
    """스킬 · 소환수 영문 이름 → 한글 (없으면 영문 그대로)."""
    if not en:
        return en
    if en in MINIONS_KO:
        return MINIONS_KO[en]
    n = _names().get(en)
    if n:
        return n
    if en.startswith("Ascended "):  # 바알 면죄 · 바알 지배로 승천한 파수꾼
        rest = ko(en[len("Ascended "):])
        if rest != en[len("Ascended "):]:
            return "승천한 " + rest
    return en


PARTS_KO = {
    "Manual Stages": "단계 직접 지정",
    "Maximum Stages": "최대 단계",
    "Max Stages": "최대 단계",
    "Stages": "단계",
}


def part_label(en: str) -> str:
    """스킬 파트 이름 (PoB 사이드바 세 번째 칸). 모르는 건 영어 그대로."""
    return PARTS_KO.get(en, en)


def is_vaal(en: str) -> bool:
    return en.startswith("Vaal ")


def skill_label(en: str) -> str:
    """'그룹 안의 스킬' 칸 표시: 바알 스킬은 따로 표시해서 구분이 쉽게."""
    k = ko(en)
    return f"{k}  (바알 스킬)" if is_vaal(en) else k


def group_label(en_label: str) -> str:
    """그룹 이름 'Vaal Absolution, Frostblink' → '바알 면죄, 서리점멸'."""
    return ", ".join(ko(x.strip()) for x in en_label.split(","))
