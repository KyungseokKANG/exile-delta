"""백그라운드 스레드에서 함수를 실행하고 결과를 GUI 스레드로 돌려준다."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

_alive: set = set()


class _Job(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, str)


def run_async(fn, on_done=None, on_error=None, on_progress=None, with_progress=False):
    """fn 을 스레드에서 실행. with_progress=True 면 fn(progress) 형태로 호출."""
    job = _Job()
    _alive.add(job)
    if on_done:
        job.done.connect(on_done)
    if on_error:
        job.failed.connect(on_error)
    if on_progress:
        job.progress.connect(on_progress)

    def finish():
        _alive.discard(job)

    job.done.connect(lambda *_: finish())
    job.failed.connect(lambda *_: finish())

    def target():
        try:
            res = fn(lambda d, t, m: job.progress.emit(int(d), int(t), str(m))) if with_progress else fn()
            job.done.emit(res)
        except Exception as e:  # noqa: BLE001
            job.failed.emit(str(e) or type(e).__name__)

    threading.Thread(target=target, daemon=True).start()
    return job
