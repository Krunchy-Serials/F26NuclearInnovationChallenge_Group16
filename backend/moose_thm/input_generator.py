"""Render procedure parameters into a user-supplied, model-specific MOOSE deck."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


REQUIRED_TEMPLATE_TOKENS = (
    "POWER_RAMP_RATE",
    "PRESSURE_RAMP_RATE",
    "BOILING_INITIATION_PRESSURE",
    "INLET_SUBCOOLING",
    "STARTUP_TYPE",
    "INITIAL_PRESSURE_MPA",
    "INITIAL_TEMPERATURE_C",
    "HOLD_COUNT",
    "HOLD_DURATION",
    "HOLD_SCHEDULE_JSON",
    "HOLD_SCHEDULE_FILE",
    "OUTPUT_CSV",
)
MAX_HOLD_POINTS = 3


def procedure_template_values(
    procedure: Any,
    *,
    output_csv_name: str,
) -> dict[str, str]:
    """Validate StartupProcedure inputs and produce string substitutions.

    The template owns all MOOSE syntax and model interpretation. This function
    only serializes requested inputs; it does not construct reactor physics.
    """
    scalar_inputs = {
        "POWER_RAMP_RATE": float(procedure.power_ramp_rate),
        "PRESSURE_RAMP_RATE": float(procedure.pressure_ramp_rate),
        "BOILING_INITIATION_PRESSURE": float(
            procedure.boiling_initiation_pressure
        ),
        "INLET_SUBCOOLING": float(procedure.inlet_subcooling),
    }
    ranges = {
        "POWER_RAMP_RATE": (0.5, 3.0),
        "PRESSURE_RAMP_RATE": (0.1, 1.0),
        "BOILING_INITIATION_PRESSURE": (0.1, 7.0),
        "INLET_SUBCOOLING": (5.0, 50.0),
    }
    for name, value in scalar_inputs.items():
        lower, upper = ranges[name]
        if not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be between {lower} and {upper}.")
    initial_pressure = float(procedure.initial_conditions.pressure_mpa)
    initial_temperature = float(procedure.initial_conditions.temperature_c)
    if (
        not math.isfinite(initial_pressure)
        or initial_pressure < 0.0
        or not math.isfinite(initial_temperature)
    ):
        raise ValueError("Startup type initial conditions must be finite and valid.")

    if Path(output_csv_name).name != output_csv_name:
        raise ValueError("output_csv_name must be a filename, not a path.")
    if not output_csv_name.lower().endswith(".csv"):
        raise ValueError("output_csv_name must use the .csv extension.")

    schedule = list(procedure.hold_schedule)
    if len(schedule) > MAX_HOLD_POINTS:
        raise ValueError(f"At most {MAX_HOLD_POINTS} hold points are supported.")
    hold_rows = []
    for point in schedule:
        power = int(point.power_percent)
        duration = float(point.duration_minutes)
        if power not in (25, 50, 75):
            raise ValueError("Hold powers must be selected from 25, 50, and 75 percent.")
        if not math.isfinite(duration) or not 0.0 <= duration <= 60.0:
            raise ValueError("Each hold duration must be between 0 and 60 minutes.")
        hold_rows.append(
            {"power_percent": power, "duration_minutes": duration}
        )

    durations = {row["duration_minutes"] for row in hold_rows}
    if len(durations) > 1:
        raise ValueError(
            "This optimizer supplies one hold_duration for all scheduled holds."
        )
    hold_duration = next(iter(durations), 0.0)
    values = {
        name: f"{value:.12g}" for name, value in scalar_inputs.items()
    }
    values.update(
        {
            "STARTUP_TYPE": procedure.startup_type.value,
            "INITIAL_PRESSURE_MPA": f"{initial_pressure:.12g}",
            "INITIAL_TEMPERATURE_C": f"{initial_temperature:.12g}",
            "HOLD_COUNT": str(len(hold_rows)),
            "HOLD_DURATION": f"{hold_duration:.12g}",
            "HOLD_SCHEDULE_JSON": json.dumps(hold_rows, separators=(",", ":")),
            "HOLD_SCHEDULE_FILE": "hold_schedule.json",
            "OUTPUT_CSV": output_csv_name,
        }
    )
    for index in range(MAX_HOLD_POINTS):
        row = hold_rows[index] if index < len(hold_rows) else None
        values[f"HOLD_{index + 1}_POWER"] = str(row["power_percent"] if row else 0)
        values[f"HOLD_{index + 1}_DURATION"] = (
            f"{row['duration_minutes']:.12g}" if row else "0"
        )
    return values


def generate_input_deck(
    procedure: Any,
    template_path: str | Path,
    output_path: str | Path,
    *,
    output_csv_name: str,
) -> Path:
    """Render a caller-provided MOOSE input template using ``{{TOKEN}}`` markers.

    The template must implement the procedure using its model's actual THM
    components, boundary conditions, controls, and validated properties. Tokens
    are data substitution only; this renderer does not supply those equations.
    """
    template_file = Path(template_path)
    if not template_file.is_file():
        raise FileNotFoundError(f"MOOSE input template does not exist: {template_file}")
    template = template_file.read_text(encoding="utf-8")
    values = procedure_template_values(procedure, output_csv_name=output_csv_name)

    missing_tokens = [
        token for token in REQUIRED_TEMPLATE_TOKENS if f"{{{{{token}}}}}" not in template
    ]
    if missing_tokens:
        raise ValueError(
            "MOOSE template is missing required tokens: "
            + ", ".join(f"{{{{{token}}}}}" for token in missing_tokens)
        )

    rendered = template
    for token, value in values.items():
        rendered = rendered.replace(f"{{{{{token}}}}}", value)
    unresolved = re.findall(r"\{\{[A-Z0-9_]+\}\}", rendered)
    if unresolved:
        raise ValueError(f"Unresolved MOOSE template tokens: {sorted(set(unresolved))}")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")
    (destination.parent / "hold_schedule.json").write_text(
        values["HOLD_SCHEDULE_JSON"] + "\n",
        encoding="utf-8",
    )
    return destination
