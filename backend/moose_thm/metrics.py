"""Metric extraction hooks for validated transient data and coupled analyses.

Implement these hooks with qualified methods, validation evidence, and the
necessary MOOSE/OpenFOAM/GeN-Foam and structural-analysis outputs before using
the backend for engineering decisions.
"""

from __future__ import annotations

from typing import Any

from .parser import TransientOutput, calculate_startup_time_minutes


def calculate_flashing_margin(transient: TransientOutput) -> float:
    """Extract a flashing margin with its state variables and pressure basis.

    The optimizer's built-in pressure thresholds are illustrative only. This
    backend must provide a validated criterion with defined units and sign.
    """
    raise NotImplementedError(
        "Implement a validated flashing-margin criterion and document its basis."
    )


def calculate_density_wave_oscillation_index(
    transient: TransientOutput,
) -> float:
    """Extract DWO index from adequately sampled flow and pressure histories."""
    raise NotImplementedError(
        "Implement a validated DWO index from sampled transient outputs."
    )


def calculate_pressure_oscillation_index(transient: TransientOutput) -> float:
    """Extract a documented pressure-oscillation metric from transient data."""
    raise NotImplementedError(
        "Implement a validated pressure-oscillation metric and units."
    )


def calculate_thermal_stress(transient: TransientOutput) -> float:
    """Extract stress from coupled structural results or validated stress data."""
    raise NotImplementedError(
        "Provide validated structural/thermal-stress results before scoring."
    )


def calculate_lost_generation_index(
    transient: TransientOutput,
    *,
    startup_time_minutes: float,
    context: dict[str, Any] | None = None,
) -> float:
    """Calculate a consistent lost-generation index from approved assumptions."""
    raise NotImplementedError(
        "Provide approved lost-generation assumptions and transient outputs."
    )


def calculate_operator_intervention_index(
    transient: TransientOutput,
    context: dict[str, Any] | None = None,
) -> float:
    """Calculate an intervention index from documented operational assumptions."""
    raise NotImplementedError(
        "Provide an approved operator-intervention method and evidence."
    )


def calculate_thermal_stress_penalty(
    transient: TransientOutput,
    *,
    thermal_stress: float,
    context: dict[str, Any] | None = None,
) -> float:
    """Map validated thermal stress to the startup-cost penalty scale."""
    raise NotImplementedError(
        "Provide an approved thermal-stress penalty mapping and units."
    )


def extract_simulation_metrics(
    transient: TransientOutput,
    *,
    cost_context: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Return the metric contract; startup cost is summed from its components."""
    startup_time = calculate_startup_time_minutes(transient)
    thermal_stress = calculate_thermal_stress(transient)
    return {
        "startup_time_minutes": startup_time,
        "flashing_margin": calculate_flashing_margin(transient),
        "density_wave_oscillation_index": (
            calculate_density_wave_oscillation_index(transient)
        ),
        "pressure_oscillation_index": calculate_pressure_oscillation_index(
            transient
        ),
        "thermal_stress": thermal_stress,
        "lost_generation_index": calculate_lost_generation_index(
            transient,
            startup_time_minutes=startup_time,
            context=cost_context,
        ),
        "operator_intervention_index": calculate_operator_intervention_index(
            transient,
            context=cost_context,
        ),
        "thermal_stress_penalty": calculate_thermal_stress_penalty(
            transient,
            thermal_stress=thermal_stress,
            context=cost_context,
        ),
    }
