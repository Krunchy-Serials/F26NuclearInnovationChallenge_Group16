"""Metric extraction hooks for validated transient data and coupled analyses.

No empirical risk functions or synthetic scores belong in this module. Complete
these hooks using qualified correlations, validation evidence, and the necessary
MOOSE/OpenFOAM/GeN-Foam and structural-analysis outputs before optimization.
"""

from __future__ import annotations

from typing import Any

from .parser import TransientOutput, calculate_startup_time_minutes


def calculate_flashing_risk(transient: TransientOutput) -> float:
    """Extract flashing risk from pressure, local saturation state, and flow.

    Required model outputs typically include local pressure, fluid temperature
    or enthalpy, vapor quality/void fraction, and mass flow versus time. Apply a
    validated flashing-instability criterion with documented normalization to
    0-100. Do not substitute a guessed pressure threshold or heuristic score.
    """
    raise NotImplementedError(
        "Implement with validated flashing criteria and transient state outputs."
    )


def calculate_density_wave_oscillation_risk(transient: TransientOutput) -> float:
    """Extract DWO risk from time-resolved two-phase flow and power signals.

    Use appropriately sampled pressure-drop, mass-flow, void/quality, and power
    histories, then apply a validated stability map or documented signal-analysis
    criterion. Include sampling adequacy and uncertainty; return a normalized
    0-100 quantity only when that mapping is scientifically defined.
    """
    raise NotImplementedError(
        "Implement with validated DWO criteria and sampled transient outputs."
    )


def calculate_geysering_risk(transient: TransientOutput) -> float:
    """Extract geysering risk from pressure, subcooling, void, and flow histories.

    Required outputs include pressure, fluid and wall temperatures (or subcooling),
    void/quality, and mass-flow time series. Use a validated geysering criterion
    and explicit event/window aggregation; do not infer risk from inputs alone.
    """
    raise NotImplementedError(
        "Implement with validated geysering criteria and transient state outputs."
    )


def calculate_thermal_stress(transient: TransientOutput) -> float:
    """Extract stress from a coupled structural solution or validated stress data.

    THM temperature and pressure traces alone are insufficient to establish
    component stress. A structural model needs geometry, constraints, material
    properties, temperature/pressure loads, and a defined stress metric; preserve
    the peak and location/time metadata when reducing its output.
    """
    raise NotImplementedError(
        "Provide validated structural/thermal-stress results before scoring."
    )


def calculate_startup_cost(
    transient: TransientOutput,
    *,
    startup_time_minutes: float,
    context: dict[str, Any] | None = None,
) -> float:
    """Calculate cost using supplied economic/operational context and outputs.

    Required assumptions/data include lost net generation over the measured
    startup, energy prices, staffing/labor rates, and any approved startup cost
    model. Keep currency, reference period, and treatment of downtime explicit.
    """
    raise NotImplementedError(
        "Provide an approved cost model and economic context before optimization."
    )


def extract_simulation_metrics(
    transient: TransientOutput,
    *,
    cost_context: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Build the optimizer metric mapping after all extraction hooks are validated."""
    startup_time = calculate_startup_time_minutes(transient)
    return {
        "startup_time_minutes": startup_time,
        "flashing_instability_risk": calculate_flashing_risk(transient),
        "density_wave_oscillation_risk": calculate_density_wave_oscillation_risk(
            transient
        ),
        "geysering_risk": calculate_geysering_risk(transient),
        "thermal_stress": calculate_thermal_stress(transient),
        "startup_cost": calculate_startup_cost(
            transient,
            startup_time_minutes=startup_time,
            context=cost_context,
        ),
    }
