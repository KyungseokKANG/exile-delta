"""PoB(Path of Building Community) 소스 설치/업데이트.

PoB 자체 업데이터처럼 manifest.xml 을 읽어 필요한 파일만 받는다.
계산에 필요 없는 이미지(트리 스프라이트 등)는 받지 않는다.
설치 위치: %LOCALAPPDATA%\\ExileDelta\\pob\\<tag>\\{src,runtime,manifest.xml}
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

REPO = "PathOfBuildingCommunity/PathOfBuilding"
from paths import LOCAL

BASE = LOCAL / "pob"
USER_DIR = BASE / "user"
UA = {"User-Agent": "ExileDelta (PoB headless installer)"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".webp", ".dds", ".tga", ".gif", ".ico"}


def _current_file() -> Path:
    return BASE / "current.txt"


def installed() -> tuple[str, Path] | None:
    """(tag, src 경로) 또는 None."""
    try:
        tag = _current_file().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    root = BASE / tag
    if tag and (root / ".complete").exists() and (root / "src" / "Launch.lua").exists():
        return tag, root / "src"
    return None


def latest_tag() -> str:
    r = requests.get(f"https://api.github.com/repos/{REPO}/releases/latest", headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()["tag_name"]


def _sha_ok(data: bytes, sha1: str) -> bool:
    if hashlib.sha1(data).hexdigest() == sha1:
        return True
    norm = re.sub(rb"\r\n?|\n", b"\r\n", data)
    return hashlib.sha1(norm).hexdigest() == sha1


def _bad_file() -> Path:
    return BASE / "bad.json"


def bad_tags() -> dict:
    """자체 점검에 실패한 버전 {tag: 이유} — 자동 업데이트에서 건너뜀."""
    import json

    try:
        return json.loads(_bad_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def mark_bad(tag: str, reason: str) -> None:
    import json

    d = bad_tags()
    d[tag] = reason[:300]
    BASE.mkdir(parents=True, exist_ok=True)
    _bad_file().write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def is_complete(tag: str) -> bool:
    root = BASE / tag
    return (root / ".complete").exists() and (root / "src" / "Launch.lua").exists()


def activate(tag: str) -> None:
    """점검을 통과한 버전으로 전환. 바로 전 버전 하나는 되돌리기용으로 남긴다."""
    cur = installed()
    prev = cur[0] if cur and cur[0] != tag else None
    _current_file().write_text(tag, encoding="utf-8")
    if prev:
        (BASE / "previous.txt").write_text(prev, encoding="utf-8")
    keep = {tag, "user", prev}
    for d in BASE.iterdir():
        if d.is_dir() and d.name not in keep and (d / ".complete").exists():
            shutil.rmtree(d, ignore_errors=True)


def rollback() -> str | None:
    """바로 전 버전으로 되돌림. 되돌린 tag 또는 None."""
    try:
        prev = (BASE / "previous.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if prev and is_complete(prev):
        cur = installed()
        if cur:
            mark_bad(cur[0], "사용자가 이전 버전으로 되돌림")
        _current_file().write_text(prev, encoding="utf-8")
        return prev
    return None


def install(tag: str, progress=None, cancelled=None, activate_now: bool = True) -> Path:
    """tag 버전을 설치하고 src 경로를 반환. progress(done, total, text).
    activate_now=False 면 받기만 하고 현재 버전은 그대로 (자동 업데이트: 점검 후 activate)."""
    progress = progress or (lambda *a: None)
    cancelled = cancelled or (lambda: False)
    root = BASE / tag
    root.mkdir(parents=True, exist_ok=True)

    progress(0, 1, "manifest 받는 중…")
    man_url = f"https://raw.githubusercontent.com/{REPO}/{tag}/manifest.xml"
    r = requests.get(man_url, headers=UA, timeout=30)
    r.raise_for_status()
    man_bytes = r.content
    tree = ET.fromstring(man_bytes)

    sources = {}
    for s in tree.iter("Source"):
        if s.get("platform") not in (None, "win32"):
            continue
        sources[s.get("part")] = s.get("url").replace("{branch}", tag)

    jobs = []
    for f in tree.iter("File"):
        part, name, sha1 = f.get("part"), f.get("name"), f.get("sha1")
        if Path(name).suffix.lower() in SKIP_EXT or part not in sources:
            continue
        if part in ("program", "tree"):
            dest = root / "src" / name
        elif part == "runtime":
            if not name.startswith("lua/"):
                continue  # dll 등 네이티브 런타임은 필요 없음
            dest = root / "runtime" / name
        else:
            continue
        jobs.append((sources[part] + name, dest, sha1))

    total = len(jobs)
    done = 0
    session = requests.Session()
    session.headers.update(UA)

    def fetch(url: str, dest: Path, sha1: str) -> None:
        if dest.exists() and _sha_ok(dest.read_bytes(), sha1):
            return
        for attempt in range(3):
            if cancelled():
                raise RuntimeError("취소됨")
            try:
                resp = session.get(url, timeout=60)
                resp.raise_for_status()
                data = resp.content
                if not _sha_ok(data, sha1):
                    raise RuntimeError(f"sha1 불일치: {dest.name}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(dest.suffix + ".tmp")
                tmp.write_bytes(data)
                os.replace(tmp, dest)
                return
            except Exception:
                if attempt == 2:
                    raise

    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = [ex.submit(fetch, *j) for j in jobs]
        for fut in as_completed(futs):
            fut.result()
            done += 1
            if done % 5 == 0 or done == total:
                progress(done, total, f"PoB {tag} 파일 받는 중… {done}/{total}")

    (root / "manifest.xml").write_bytes(man_bytes)
    (root / ".complete").write_text(tag, encoding="utf-8")
    if activate_now:
        activate(tag)
    progress(total, total, f"PoB {tag} 설치 완료")
    return root / "src"
