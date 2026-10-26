"""Typed builders for test data: pyarrow-stubs leaves parts of pa.array and pa.table unknown."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pyarrow as pa

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

_pa: Any = pa


def array(values: Sequence[object], type: pa.DataType | None = None) -> pa.Array[Any]:  # noqa: A002
    return _pa.array(values, type)


def table(columns: Mapping[str, Sequence[object] | pa.Array[Any]]) -> pa.Table:
    return _pa.table(columns)


def where(source: pa.Table, mask: Sequence[bool]) -> pa.Table:
    """The rows of ``source`` where ``mask`` is true."""
    return _pa.Table.filter(source, _pa.array(mask))


def chunked(*parts: Mapping[str, Sequence[object]]) -> pa.Table:
    """A table with one chunk per part."""
    return _pa.Table.from_batches([_pa.record_batch(part) for part in parts])
