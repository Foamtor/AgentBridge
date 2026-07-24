"""In-process Prometheus text exposition (no prometheus_client dep)."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock


def _label_key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{v}"' for k, v in labels)
    return "{" + inner + "}"


class PrometheusMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = (
            defaultdict(lambda: defaultdict(float))
        )
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], list[float]]] = (
            defaultdict(lambda: defaultdict(list))
        )

    def inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        value: float = 1.0,
    ) -> None:
        key = _label_key(labels)
        with self._lock:
            self._counters[name][key] += value

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
    ) -> None:
        key = _label_key(labels)
        with self._lock:
            self._histograms[name][key].append(value)

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            for name, series in sorted(self._counters.items()):
                lines.append(f"# TYPE {name} counter")
                for labels, val in sorted(series.items()):
                    lines.append(f"{name}{_format_labels(labels)} {val}")
            for name, series in sorted(self._histograms.items()):
                lines.append(f"# TYPE {name} summary")
                for labels, samples in sorted(series.items()):
                    if not samples:
                        continue
                    lbl = _format_labels(labels)
                    count = len(samples)
                    total = sum(samples)
                    # summary without quantile labels: _count / _sum
                    base = name
                    lines.append(f"{base}_count{lbl} {count}")
                    lines.append(f"{base}_sum{lbl} {total}")
        return "\n".join(lines) + ("\n" if lines else "")
