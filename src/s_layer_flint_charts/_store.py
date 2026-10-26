"""Keep query results and assembled charts per conversation, for the tools and the endpoints."""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from s_layer_flint_charts._rows import DEFAULT_ROW_CAP

if TYPE_CHECKING:
    import datetime
    from collections.abc import Callable

    from s_layer_flint_charts._grain import Metric
    from s_layer_flint_charts._mapping import FieldType
    from s_layer_flint_charts._rows import ChartRows

__all__ = ["ChartSession", "ChartStore", "Column", "StoredChart", "StoredResult"]


@dataclass(frozen=True, kw_only=True)
class Column:
    """
    One column of a stored result: its Flint type, and its additivity when it is a metric.

    ``metric`` is ``None`` for a dimension.
    """

    name: str
    field_type: FieldType
    metric: Metric | None = None
    description: str | None = None

    @property
    def kind(self) -> Literal["metric", "dimension"]:
        """Whether the column is a metric or a dimension."""
        return "dimension" if self.metric is None else "metric"


@dataclass(frozen=True, kw_only=True)
class StoredResult:
    """
    A query result, converted once into the rows a chart draws.

    ``cap`` is the most rows a chart of it may draw, the same cap the result was cut at.
    """

    result_id: str
    view: str
    columns: dict[str, Column]
    rows: ChartRows
    queried_at: datetime.datetime
    cap: int = DEFAULT_ROW_CAP

    @property
    def metrics(self) -> dict[str, Metric]:
        """The metric columns, for :func:`check_grain`."""
        return {
            name: metric
            for name, column in self.columns.items()
            if (metric := column.metric) is not None
        }


@dataclass(frozen=True, kw_only=True)
class StoredChart:
    """
    The rows one chart draws, for the browser to fetch by the chart's ``data.url``.

    They are kept per chart rather than per result: the grain guard may add zeros to a stacked
    area, and a percentage may go out as points. ``rows`` is the JSON array the validator saw.
    """

    chart_id: str
    result_id: str
    rows: bytes


class ChartSession:
    """
    The results and charts of one conversation.

    The oldest entries are dropped once there are more than ``max_results`` results or
    ``max_charts`` charts, so a long conversation does not hold every result it ever ran.
    """

    def __init__(self, *, max_results: int = 20, max_charts: int = 50) -> None:
        self._results: OrderedDict[str, StoredResult] = OrderedDict()
        self._charts: OrderedDict[str, StoredChart] = OrderedDict()
        self._max_results = max_results
        self._max_charts = max_charts
        self._lock = threading.Lock()

    def new_result_id(self) -> str:
        """An unguessable id for a result about to be stored."""
        return f"r_{secrets.token_urlsafe(9)}"

    def new_chart_id(self) -> str:
        """An unguessable id for a chart about to be stored."""
        return f"c_{secrets.token_urlsafe(9)}"

    def add_result(self, result: StoredResult) -> None:
        """Keep a result, dropping the oldest past the limit."""
        with self._lock:
            self._results[result.result_id] = result
            while len(self._results) > self._max_results:
                self._results.popitem(last=False)

    def result(self, result_id: str) -> StoredResult | None:
        """A stored result, or ``None`` when there is none by that id (or it was dropped)."""
        with self._lock:
            return self._results.get(result_id)

    def add_chart(self, chart: StoredChart) -> None:
        """Keep a chart, dropping the oldest past the limit."""
        with self._lock:
            self._charts[chart.chart_id] = chart
            while len(self._charts) > self._max_charts:
                self._charts.popitem(last=False)

    def chart(self, chart_id: str) -> StoredChart | None:
        """A stored chart, or ``None`` when there is none by that id (or it was dropped)."""
        with self._lock:
            return self._charts.get(chart_id)


class ChartStore:
    """
    One :class:`ChartSession` per conversation, forgotten after ``ttl`` seconds unused.

    The app decides what a session id is (a conversation id, a signed cookie); the store only
    keeps the results of one session away from every other.
    """

    def __init__(
        self,
        *,
        ttl: float = 3600,
        max_sessions: int = 1000,
        max_results: int = 20,
        max_charts: int = 50,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sessions: OrderedDict[str, tuple[ChartSession, float]] = OrderedDict()
        self._ttl = ttl
        self._max_sessions = max_sessions
        self._max_results = max_results
        self._max_charts = max_charts
        self._clock = clock
        self._lock = threading.Lock()

    def session(self, session_id: str) -> ChartSession:
        """The session by this id, made when there is none, and marked as used now."""
        with self._lock:
            now = self._clock()
            self._expire(now)
            entry = self._sessions.pop(session_id, None)
            session = (
                entry[0]
                if entry is not None
                else ChartSession(max_results=self._max_results, max_charts=self._max_charts)
            )
            self._sessions[session_id] = (session, now)
            while len(self._sessions) > self._max_sessions:
                self._sessions.popitem(last=False)
            return session

    def get(self, session_id: str) -> ChartSession | None:
        """The session by this id if it is still kept, without making one."""
        with self._lock:
            self._expire(self._clock())
            entry = self._sessions.get(session_id)
            return None if entry is None else entry[0]

    def _expire(self, now: float) -> None:
        # Sessions are ordered by last use, so the stale ones are at the front.
        while self._sessions:
            _, (_, used) = next(iter(self._sessions.items()))
            if now - used <= self._ttl:
                break
            self._sessions.popitem(last=False)
