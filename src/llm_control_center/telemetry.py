from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


def new_trace_id() -> str:
    return f"tr_{uuid.uuid4().hex}"


def now_epoch_seconds() -> int:
    return int(time.time())


@dataclass(frozen=True)
class TimerResult:
    started_at: float
    ended_at: float

    @property
    def latency_ms(self) -> int:
        return int((self.ended_at - self.started_at) * 1000)


@contextmanager
def timer() -> Iterator[TimerResult]:
    result = TimerResult(started_at=time.perf_counter(), ended_at=0.0)
    try:
        yield result
    finally:
        object.__setattr__(result, "ended_at", time.perf_counter())
