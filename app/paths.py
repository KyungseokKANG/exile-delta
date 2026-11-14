"""앱 데이터 폴더 위치 (한 곳에서 관리).

- ROAMING = %APPDATA%\\ExileDelta        설정 · 캐릭터 · 번역 사전 갱신본
- LOCAL   = %LOCALAPPDATA%\\ExileDelta   PoB 엔진 · 로그 · 캐시

예전 이름(Exile Sieve) 폴더가 있으면 처음 실행할 때 새 이름으로 옮긴다 (migrate).
옮기지 못하면(예전 버전이 아직 실행 중 등) 예전 폴더를 그대로 쓴다 → 데이터가 사라지지 않음.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Exile Delta"
DIR_NAME = "ExileDelta"
OLD_DIR_NAMES = ("ExileSieve",)


def _root(env: str) -> Path:
    return Path(os.environ.get(env) or Path.home())


def _pick(env: str) -> Path:
    new = _root(env) / DIR_NAME
    if new.exists():
        return new
    for old_name in OLD_DIR_NAMES:
        old = _root(env) / old_name
        if old.exists():
            try:
                os.rename(old, new)  # 같은 드라이브라 순식간 (PoB 엔진 370MB 도 다시 받지 않음)
                return new
            except OSError:
                return old  # 예전 버전이 파일을 쥐고 있음 → 다음 실행 때 다시 시도
    return new


ROAMING = _pick("APPDATA")
LOCAL = _pick("LOCALAPPDATA")
