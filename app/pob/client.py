"""GUI 쪽 PoB 워커 클라이언트 (Qt, 비동기)."""
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer

from pob import installer

WORKER_LOG = installer.BASE.parent / "pob_worker.log"


def worker_command() -> tuple[str, list[str]]:
    if getattr(sys, "frozen", False):
        return sys.executable, []
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    return sys.executable, [str(main_py)]


class PobClient(QObject):
    # missing(미설치) / starting / ready / error / stopped
    stateChanged = Signal(str, str)
    busyChanged = Signal(bool)  # 계산 요청이 남아 있는지 (화면 '계산 중…' 표시)

    def __init__(self, parent=None, override: tuple[str, Path] | None = None, log: Path | None = None):
        super().__init__(parent)
        self.override = override  # (tag, src) — 자동 업데이트 자체 점검용 (설치는 됐지만 아직 사용 전인 버전)
        self.log_path = log or WORKER_LOG
        self.state = "stopped"
        self.version = ""
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_conn)
        self._proc: QProcess | None = None
        self._sock = None
        self._buf = b""
        self._next = 1
        self._pending: dict[int, tuple] = {}  # rid → (ok, err, background)
        self._queue: list[bytes] = []
        self._busy = False
        # 백그라운드(기여도·젬 영향 등 오래 걸리는 자동 계산): 한 번에 한 조각만, 다른 요청이 없을 때만 보냄
        # → Ctrl+C 비교·장비 변경 같은 요청이 긴 계산 뒤에 줄 서지 않음
        self._bg: deque = deque()
        self._bg_inflight = False

    def fg_pending(self) -> bool:
        """사용자 요청(백그라운드 제외)이 처리 중인지."""
        return any(not bg for _, _, bg in self._pending.values())

    def _update_busy(self) -> None:
        b = self.fg_pending()
        if b != self._busy:
            self._busy = b
            self.busyChanged.emit(b)

    # ---- 수명 ----
    def _set_state(self, st: str, msg: str = "") -> None:
        self.state = st
        self.stateChanged.emit(st, msg)

    def start(self) -> None:
        inst = self.override or installer.installed()
        if not inst:
            self._set_state("missing", "PoB 엔진이 설치되지 않았습니다")
            return
        self.stop()
        self.version, src = inst
        if not self._server.isListening():
            self._server.listen(QHostAddress.SpecialAddress.LocalHost, 0)
        prog, args = worker_command()
        self._proc = QProcess(self)
        self._proc.finished.connect(self._on_exit)
        self._proc.start(prog, args + ["--pob-worker", str(self._server.serverPort()), str(self.log_path)])
        self._set_state("starting", f"PoB {self.version} 엔진 시작 중…")
        try:
            from storage import load_settings

            minion = bool(load_settings().get("minion_in_main", True))
        except Exception:  # noqa: BLE001
            minion = True
        self._init_args = {"src": str(src), "user": str(installer.USER_DIR), "minion_in_main": minion}

    def stop(self) -> None:
        if self._sock is not None:
            self._sock.disconnectFromHost()
            self._sock = None
        if self._proc is not None:
            self._proc.finished.disconnect(self._on_exit)
            self._proc.kill()
            self._proc.waitForFinished(2000)
            self._proc = None
        for _, (_, err, _bg) in list(self._pending.items()):
            if err:
                err("엔진이 중지되었습니다")
        self._pending.clear()
        self._queue.clear()
        self._bg.clear()
        self._bg_inflight = False
        self._buf = b""
        self._update_busy()

    def _on_exit(self, code, _status) -> None:
        self._proc = None
        self._sock = None
        for _, (_, err, _bg) in list(self._pending.items()):
            if err:
                err("PoB 엔진 프로세스가 종료되었습니다")
        self._pending.clear()
        self._bg.clear()
        self._bg_inflight = False
        self._update_busy()
        self._set_state("error", f"PoB 엔진이 종료되었습니다 (code {code}). 로그: {self.log_path}")

    def _on_conn(self) -> None:
        sock = self._server.nextPendingConnection()
        if self._sock is not None:
            sock.close()
            return
        self._sock = sock
        sock.readyRead.connect(self._on_read)
        self._send_raw("init", self._init_args, self._on_init_ok, self._on_init_err, front=True)

    def _on_init_ok(self, _r) -> None:
        self._set_state("ready", f"PoB {self.version} 엔진 준비됨")
        for data in self._queue:
            self._sock.write(data)
        self._queue.clear()
        self._pump()

    def _on_init_err(self, msg: str) -> None:
        self._set_state("error", f"PoB 엔진 초기화 실패: {msg}")

    # ---- 통신 ----
    def _send_raw(self, cmd, args, ok, err, front=False, bg=False) -> None:
        rid = self._next
        self._next += 1
        self._pending[rid] = (ok, err, bg)
        self._update_busy()
        data = json.dumps({"id": rid, "cmd": cmd, "args": args}, ensure_ascii=False).encode("utf-8") + b"\n"
        if self._sock is not None and (front or self.state == "ready"):
            self._sock.write(data)
        else:
            self._queue.append(data)

    def call(self, cmd: str, args: dict, ok=None, err=None, background: bool = False) -> None:
        if self.state in ("missing", "error", "stopped"):
            if err:
                err("PoB 엔진이 실행 중이 아닙니다")
            return
        if background:
            self._bg.append((cmd, args, ok, err))
            self._pump()
            return
        self._send_raw(cmd, args, ok, err)

    def _pump(self) -> None:
        """백그라운드 요청 한 조각을 보냄 (사용자 요청이 없고, 보낸 조각이 끝났을 때만)."""
        if self._bg_inflight or not self._bg or self.state != "ready" or self._sock is None or self.fg_pending():
            return
        cmd, args, ok, err = self._bg.popleft()
        self._bg_inflight = True

        def wrap(fn):
            def w(x):
                self._bg_inflight = False
                if fn:
                    fn(x)
            return w
        self._send_raw(cmd, args, wrap(ok), wrap(err), bg=True)

    def call_chunks(self, cmd: str, args: dict, limit: int, ok, err, alive=lambda: True) -> None:
        """skip/limit 로 나눠 백그라운드로 계산하고 합쳐서 ok(전체) — 조각 사이에 다른 요청이 끼어들 수 있음.
        alive() 가 False 가 되면(빌드가 바뀜 등) 중단하고 err(None)."""
        acc: dict = {}

        def step(skip: int) -> None:
            self.call(cmd, dict(args, skip=skip, limit=limit), got, err, background=True)

        def got(r):
            if not alive():
                if err:
                    err(None)
                return
            r = r or {}
            for k, v in r.items():
                if k == "next":
                    continue
                if k not in acc:
                    acc[k] = v
                elif isinstance(v, list) and isinstance(acc[k], list):
                    acc[k].extend(v)
                elif isinstance(v, dict) and isinstance(acc[k], dict) and k != "base":
                    acc[k].update(v)
            if r.get("next") is not None:
                step(int(r["next"]))
            else:
                ok(acc)
        step(0)

    def _on_read(self) -> None:
        self._buf += bytes(self._sock.readAll())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            ok, err, _bg = self._pending.pop(msg.get("id"), (None, None, False))
            try:
                if msg.get("ok"):
                    if ok:
                        ok(msg.get("result"))
                elif err:
                    err(msg.get("error") or "알 수 없는 오류")
            finally:
                self._update_busy()
                self._pump()
