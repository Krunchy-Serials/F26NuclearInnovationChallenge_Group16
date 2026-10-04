"""Rank illustrative operating conditions by Type 2 instability susceptibility.

This comparative engineering framework uses qualitative trends discussed in
BWR density-wave instability literature. Its score coefficients and example
conditions are transparent project assumptions, not published correlations
or BWRX-300 design data. It does not simulate reactor physics and is not a
validated reactor simulation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import math


REFERENCE_FEEDWATER_TEMPERATURE_C = 180.0
FEEDWATER_SUBCOOLING_FACTOR = 0.25
REFERENCE_INLET_SUBCOOLING_C = 12.0
REFERENCE_POWER_TO_FLOW_RATIO = 1.0
REFERENCE_ORIFICE_PRESSURE_DROP_KPA = 20.0

# These sensitivities create an interpretable, relative 0-100 index only.
SUBCOOLING_POINTS_PER_C = 1.5
POWER_TO_FLOW_POINTS_PER_UNIT = 30.0
ORIFICE_POINTS_PER_KPA = 0.35


@dataclass(frozen=True)
class OperatingCondition:
    """Inputs to the comparative score (subcooling in C, pressure drop in kPa).

    inlet_subcooling is the nominal value at the reference feedwater
    temperature. The separate feedwater adjustment is an illustrative
    bookkeeping assumption, not a thermal-hydraulic calculation.
    """

    inlet_subcooling: float
    power_to_flow_ratio: float
    feedwater_temperature: float
    inlet_orifice_pressure_drop: float

    def __post_init__(self) -> None:
        values = (
            self.inlet_subcooling,
            self.power_to_flow_ratio,
            self.feedwater_temperature,
            self.inlet_orifice_pressure_drop,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("All operating-condition inputs must be finite.")
        if self.inlet_subcooling < 0:
            raise ValueError("inlet_subcooling must be non-negative.")
        if self.power_to_flow_ratio <= 0:
            raise ValueError("power_to_flow_ratio must be greater than zero.")
        if self.feedwater_temperature < 0:
            raise ValueError("feedwater_temperature must be non-negative.")
        if self.inlet_orifice_pressure_drop < 0:
            raise ValueError("inlet_orifice_pressure_drop must be non-negative.")

    @property
    def effective_subcooling(self) -> float:
        """Apply the illustrative feedwater-temperature/subcooling adjustment."""
        return self.inlet_subcooling - FEEDWATER_SUBCOOLING_FACTOR * (
            self.feedwater_temperature - REFERENCE_FEEDWATER_TEMPERATURE_C
        )


@dataclass(frozen=True)
class StabilityResult:
    """Comparative result; higher index means greater heuristic susceptibility."""

    effective_subcooling: float
    type2_stability_index: float


def calculate_type2_stability_index(condition: OperatingCondition) -> StabilityResult:
    """Return an illustrative susceptibility score clamped to the 0-100 range.

    Greater inlet subcooling and power-to-flow ratio increase the score;
    greater inlet-orifice pressure drop decreases it. Feedwater temperature
    acts only through the assumed effective-subcooling adjustment.
    """
    raw_index = (
        50.0
        + SUBCOOLING_POINTS_PER_C
        * (condition.effective_subcooling - REFERENCE_INLET_SUBCOOLING_C)
        + POWER_TO_FLOW_POINTS_PER_UNIT
        * (condition.power_to_flow_ratio - REFERENCE_POWER_TO_FLOW_RATIO)
        - ORIFICE_POINTS_PER_KPA
        * (
            condition.inlet_orifice_pressure_drop
            - REFERENCE_ORIFICE_PRESSURE_DROP_KPA
        )
    )
    return StabilityResult(
        effective_subcooling=condition.effective_subcooling,
        type2_stability_index=max(0.0, min(100.0, raw_index)),
    )


def build_comparison() -> tuple[tuple[str, OperatingCondition], ...]:
    """Return illustrative inputs, not official BWRX-300 operating conditions."""
    return (
        (
            "Baseline BWRX-300 (illustrative)",
            OperatingCondition(
                inlet_subcooling=12.0,
                power_to_flow_ratio=1.00,
                feedwater_temperature=180.0,
                inlet_orifice_pressure_drop=20.0,
            ),
        ),
        (
            "Optimized Case (illustrative)",
            OperatingCondition(
                inlet_subcooling=8.0,
                power_to_flow_ratio=0.88,
                feedwater_temperature=190.0,
                inlet_orifice_pressure_drop=30.0,
            ),
        ),
    )


def print_report(
    comparison: tuple[tuple[str, OperatingCondition], ...] | None = None,
) -> None:
    """Print the two-case comparison and relative improvement summary."""
    cases = comparison or build_comparison()
    results = [
        (name, condition, calculate_type2_stability_index(condition))
        for name, condition in cases
    ]

    print("Type2 Stability Index (higher = greater heuristic susceptibility)")
    print(
        "Comparative engineering framework only; not a validated reactor "
        "simulation or prediction."
    )
    print()
    print(
        f"{'Rank':>4} {'Case':37} {'Subcooling (C)':>15} {'P/F ratio':>11} "
        f"{'Feedwater (C)':>14} {'Orifice dP (kPa)':>17} {'Index':>8}"
    )
    ranked_results = sorted(
        results,
        key=lambda row: row[2].type2_stability_index,
        reverse=True,
    )
    for rank, (name, condition, result) in enumerate(ranked_results, start=1):
        print(
            f"{rank:4} {name:37} {result.effective_subcooling:15.2f} "
            f"{condition.power_to_flow_ratio:11.3f} "
            f"{condition.feedwater_temperature:14.2f} "
            f"{condition.inlet_orifice_pressure_drop:17.2f} "
            f"{result.type2_stability_index:8.2f}"
        )

    if len(results) != 2:
        raise ValueError("Improvement Summary requires exactly two cases.")
    baseline = results[0][2].type2_stability_index
    optimized = results[1][2].type2_stability_index
    difference = baseline - optimized
    if baseline > 0:
        percent_reduction = difference / baseline * 100.0
        comparison_text = f"{percent_reduction:.1f}% lower than baseline"
    else:
        comparison_text = "percentage reduction undefined (baseline index is zero)"

    print("\nImprovement Summary")
    if difference > 0:
        print(
            f"Optimized Case reduces the illustrative susceptibility index by "
            f"{difference:.2f} points ({comparison_text})."
        )
    elif difference < 0:
        print(
            f"Optimized Case increases the illustrative susceptibility index "
            f"by {-difference:.2f} points."
        )
    else:
        print("Optimized Case has the same illustrative susceptibility index.")
    print(
        "This comparison reflects only the stated heuristic trends and "
        "assumptions; it does not establish operating limits or actual "
        "reactor stability."
    )


def print_literature_summary() -> None:
    """Report public evidence status without calculating heuristic scores."""
    print("Type II BWR stability: public evidence status")
    print(
        "No validated BWRX-300 Type II stability result is calculated. "
        "The available public sources do not provide a runnable model and "
        "machine-readable low-flow stability measurements together."
    )
    print()
    print(
        "NUREG/CR-2998 describes LAPUR-IV comparisons for 17 low-flow "
        "conditions at Peach Bottom 2 and Vermont Yankee, using decay ratio "
        "and natural frequency. It is a published benchmark reference, not "
        "a TRACE/RELAP5 input package."
    )
    print(
        "The public VERA Peach Bottom 2 inputs are static neutronics cases; "
        "they are not transient flow/pressure traces for density-wave analysis."
    )
    print(
        "See public_bwr_benchmark_review.md for source links, limitations, "
        "and the recommended validation path."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Review public Type II BWR stability evidence. The optional "
            "illustrative score is not a reactor simulation."
        )
    )
    parser.add_argument(
        "--illustrative",
        action="store_true",
        help=(
            "Print the project-assumption comparison score. This is not "
            "literature-derived or predictive."
        ),
    )
    args = parser.parse_args()
    if args.illustrative:
        print_report()
    else:
        print_literature_summary()


if __name__ == "__main__":
    main()
