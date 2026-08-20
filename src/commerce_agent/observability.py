from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import monotonic
from uuid import UUID

correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


@dataclass(slots=True)
class MetricsRegistry:
    counters: Counter[str] = field(default_factory=Counter)
    durations: dict[str, list[float]] = field(default_factory=dict)

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    def observe(self, name: str, value: float) -> None:
        self.durations.setdefault(name, []).append(value)


@contextmanager
def trace_operation(name: str, correlation_id: UUID, metrics: MetricsRegistry) -> Iterator[None]:
    token = correlation_id_context.set(str(correlation_id))
    started = monotonic()
    try:
        yield
        metrics.increment(f"{name}.succeeded")
    except Exception:
        metrics.increment(f"{name}.failed")
        raise
    finally:
        metrics.observe(f"{name}.duration_seconds", monotonic() - started)
        correlation_id_context.reset(token)
