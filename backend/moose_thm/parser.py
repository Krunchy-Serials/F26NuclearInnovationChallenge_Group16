"""Parse transient CSV output written by a configured MOOSE THM input deck."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TransientColumnMap:
    """CSV column names emitted by the user-supplied MOOSE model template."""

    time: str = "time"
    power: str = "power"
    pressure: str = "pressure"
    void_fraction: str = "void_fraction"
    mass_flow: str = "mass_flow"
    fluid_temperature: str = "fluid_temperature"
    cladding_temperature: str = "cladding_temperature"
    time_unit: str = "s"
    completion_power: float | None = None

    def __post_init__(self) -> None:
        if self.time_unit not in {"s", "min", "h"}:
            raise ValueError("time_unit must be one of: s, min, h.")
        if self.completion_power is not None and self.completion_power <= 0:
            raise ValueError("completion_power must be greater than zero.")


@dataclass(frozen=True)
class TransientOutput:
    """Raw, parsed time-series data and its source file."""

    data: pd.DataFrame
    source_path: Path
    columns: TransientColumnMap


def parse_transient_csv(
    csv_path: str | Path,
    columns: TransientColumnMap,
) -> TransientOutput:
    """Read a MOOSE CSV file and verify the configured time and power columns.

    The CSV must contain a combined transient table. If a model emits multiple
    files, configure its output object to write the needed postprocessors into
    one table or add a model-specific parser before using the metric hooks.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"MOOSE transient CSV was not produced: {path}")
    frame = pd.read_csv(path)
    required = {columns.time, columns.power}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"MOOSE CSV is missing required columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError(f"MOOSE transient CSV contains no data: {path}")

    for name in (columns.time, columns.power):
        frame[name] = pd.to_numeric(frame[name], errors="raise")
        if not np.isfinite(frame[name].to_numpy(dtype=float)).all():
            raise ValueError(f"MOOSE CSV column {name!r} contains non-finite values.")
    times = frame[columns.time].to_numpy(dtype=float)
    if np.any(np.diff(times) < 0.0):
        raise ValueError("MOOSE transient time values must be nondecreasing.")
    return TransientOutput(frame, path.resolve(), columns)


def calculate_startup_time_minutes(transient: TransientOutput) -> float:
    """Interpolate when the configured power trace first reaches completion power.

    Completion threshold and power units are supplied by the user/model; this
    function does not infer rated power or a BWRX-300 operating target.
    """
    columns = transient.columns
    if columns.completion_power is None:
        raise ValueError("Configure MOOSE_COMPLETION_POWER before extracting startup time.")

    times = transient.data[columns.time].to_numpy(dtype=float)
    power = transient.data[columns.power].to_numpy(dtype=float)
    reached = np.flatnonzero(power >= columns.completion_power)
    if reached.size == 0:
        raise ValueError(
            "Transient power never reached the configured startup completion threshold."
        )
    end_index = int(reached[0])
    if end_index == 0:
        completion_time = times[0]
    else:
        t0, t1 = times[end_index - 1], times[end_index]
        p0, p1 = power[end_index - 1], power[end_index]
        completion_time = (
            t1
            if p1 == p0
            else t0 + (columns.completion_power - p0) * (t1 - t0) / (p1 - p0)
        )

    factor_to_minutes = {"s": 1.0 / 60.0, "min": 1.0, "h": 60.0}
    return float((completion_time - times[0]) * factor_to_minutes[columns.time_unit])
