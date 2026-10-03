"""Screening-level burnup study for the GEH BWRX-300 design.

Design defaults reflect the Appendix A values supplied for the BWRX-300 General
Description. Cycle scheduling, fuel-cycle price, and degradation penalties are
transparent study assumptions; they are not vendor operating limits or safety
analysis results.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BWRX300Baseline:
    """BWRX-300 reference data and explicitly configurable study assumptions."""

    thermal_power_mwth: float = 870.0
    fuel_assemblies: int = 240
    assembly_mass_kg: float = 299.0
    total_uranium_mass_kg: float = 44_760.0
    core_discharge_burnup_reference: float = 50.0
    average_enrichment: float = 3.81
    max_enrichment: float = 4.95
    fuel_type: str = "GNF2"
    fuel_material: str = "UO2"
    cladding: str = "Zircaloy-2"
    capacity_factor: float = 0.90
    thermal_to_electric_efficiency: float = 0.33
    design_life_years: int = 60
    minimum_cycle_months: float = 12.0
    maximum_cycle_months: float = 24.0
    fuel_cost_per_kg_u_usd: float = 1_606.0
    reliability_threshold_gwd_mtu: float = 55.0


BASELINE = BWRX300Baseline()
DEFAULT_BURNUP_VALUES = (40.0, 45.0, 50.0, 55.0, 60.0, 65.0)
SCORE_WEIGHTS = {
    "fuel_utilization_score": 0.35,
    "cycle_length_score": 0.30,
    "economic_score": 0.20,
    "safety_margin_score": 0.15,
}
RECOMMENDATION_SCORE_FRACTION = 0.95


def _validate_burnup(burnup: float) -> float:
    """Return a finite, positive burnup value or raise a useful error."""
    value = float(burnup)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("Burnup must be finite and greater than zero.")
    return value


def _validate_baseline(baseline: BWRX300Baseline) -> None:
    """Validate the physical and economic inputs needed by the study."""
    if baseline.fuel_assemblies <= 0 or baseline.total_uranium_mass_kg <= 0.0:
        raise ValueError("Fuel inventory must be greater than zero.")
    if baseline.thermal_power_mwth <= 0.0:
        raise ValueError("Thermal power must be greater than zero.")
    if not 0.0 < baseline.capacity_factor <= 1.0:
        raise ValueError("Capacity factor must be in the range (0, 1].")
    if not 0.0 < baseline.thermal_to_electric_efficiency <= 1.0:
        raise ValueError("Thermal-to-electric efficiency must be in the range (0, 1].")
    if baseline.fuel_cost_per_kg_u_usd < 0.0:
        raise ValueError("Fuel-cycle cost per kgU cannot be negative.")


def cycle_length_months(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
) -> float:
    """Estimate a 12-24 month cycle, calibrated to 24 months at reference burnup.

    The linear relationship is a scheduling proxy, not a vendor cycle design.
    """
    burnup_value = _validate_burnup(burnup)
    return min(
        baseline.maximum_cycle_months,
        max(
            baseline.minimum_cycle_months,
            baseline.maximum_cycle_months
            * burnup_value
            / baseline.core_discharge_burnup_reference,
        ),
    )


def annual_energy(baseline: BWRX300Baseline = BASELINE) -> float:
    """Return annual net electric generation in MWh at fixed power and capacity factor."""
    _validate_baseline(baseline)
    return (
        baseline.thermal_power_mwth
        * 8_760.0
        * baseline.capacity_factor
        * baseline.thermal_to_electric_efficiency
    )


def _annual_thermal_energy_mwh(baseline: BWRX300Baseline) -> float:
    """Return annual thermal generation in MWhth."""
    return baseline.thermal_power_mwth * 8_760.0 * baseline.capacity_factor


def _uranium_mass_per_assembly_kg(baseline: BWRX300Baseline) -> float:
    """Allocate the specified core uranium inventory uniformly by assembly."""
    return baseline.total_uranium_mass_kg / baseline.fuel_assemblies


def bundles_replaced(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
    *,
    cycle_months: float | None = None,
) -> float:
    """Estimate assemblies replaced per cycle from energy and discharge burnup.

    One GWd/MTU corresponds to 24 MWhth/kgU. This energy balance uses the
    specified uranium inventory per assembly, not total assembly mass.
    """
    burnup_value = _validate_burnup(burnup)
    _validate_baseline(baseline)
    cycle_duration = (
        cycle_length_months(burnup_value, baseline)
        if cycle_months is None
        else float(cycle_months)
    )
    if not baseline.minimum_cycle_months <= cycle_duration <= baseline.maximum_cycle_months:
        raise ValueError("cycle_months must be within the 12-24 month study range.")
    cycle_years = cycle_duration / 12.0
    cycle_energy_mwhth = _annual_thermal_energy_mwh(baseline) * cycle_years
    uranium_replaced_kg = cycle_energy_mwhth / (burnup_value * 24.0)
    return min(
        float(baseline.fuel_assemblies),
        uranium_replaced_kg / _uranium_mass_per_assembly_kg(baseline),
    )


def annualized_fuel_cost(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
) -> float:
    """Estimate annualized fuel-cycle cost in USD from discharged kgU per year."""
    burnup_value = _validate_burnup(burnup)
    _validate_baseline(baseline)
    annual_uranium_replaced_kg = _annual_thermal_energy_mwh(baseline) / (
        burnup_value * 24.0
    )
    return annual_uranium_replaced_kg * baseline.fuel_cost_per_kg_u_usd


def energy_generated_per_core_cycle(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
    *,
    electric: bool = True,
) -> float:
    """Estimate core-cycle energy in MWhth or net MWh electric from burnup."""
    burnup_value = _validate_burnup(burnup)
    _validate_baseline(baseline)
    energy_mwhth = (
        burnup_value
        * (baseline.total_uranium_mass_kg / 1_000.0)
        * 24.0
        * 1_000.0
    )
    if electric:
        return energy_mwhth * baseline.thermal_to_electric_efficiency
    return energy_mwhth


def energy_generated_per_kg_uranium(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
    *,
    electric: bool = True,
) -> float:
    """Estimate MWh generated per kgU at the specified discharge burnup."""
    burnup_value = _validate_burnup(burnup)
    efficiency = baseline.thermal_to_electric_efficiency if electric else 1.0
    return burnup_value * 24.0 * efficiency


def fuel_replacements_over_60_year_lifetime(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
) -> float:
    """Estimate lifetime reload bundle-equivalents, including fractional cycles."""
    cycle_years = cycle_length_months(burnup, baseline) / 12.0
    return (
        baseline.design_life_years
        / cycle_years
        * bundles_replaced(burnup, baseline)
    )


def calculate_metrics(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
) -> dict[str, float]:
    """Calculate cycle, reload, energy, utilization, and fuel-cost metrics."""
    burnup_value = _validate_burnup(burnup)
    cycle_months = cycle_length_months(burnup_value, baseline)
    replacement_count = bundles_replaced(
        burnup_value,
        baseline,
        cycle_months=cycle_months,
    )
    cycle_cost = (
        replacement_count
        * _uranium_mass_per_assembly_kg(baseline)
        * baseline.fuel_cost_per_kg_u_usd
    )
    annual_cost = annualized_fuel_cost(burnup_value, baseline)
    annual_generation = annual_energy(baseline)
    return {
        "burnup_gwd_mtu": burnup_value,
        "cycle_length_months": cycle_months,
        "bundles_replaced": replacement_count,
        "fuel_mass_replaced_per_cycle_kg": (
            replacement_count * baseline.assembly_mass_kg
        ),
        "outages_per_year": 12.0 / cycle_months,
        "annual_energy_mwh_e": annual_generation,
        "fuel_cycle_cost_per_cycle_usd": cycle_cost,
        "annualized_fuel_cost_usd": annual_cost,
        "cost_per_mwh_usd": annual_cost / annual_generation,
        "fuel_utilization_mwh_e_per_kg_u": energy_generated_per_kg_uranium(
            burnup_value, baseline
        ),
        "core_cycle_energy_mwh_e": energy_generated_per_core_cycle(
            burnup_value, baseline
        ),
        "replacements_over_60_year_life": fuel_replacements_over_60_year_lifetime(
            burnup_value, baseline
        ),
        "fuel_reliability_penalty": fuel_reliability_penalty(
            burnup_value, baseline
        ),
        "cladding_degradation_score": cladding_degradation_score(burnup_value),
        "regulatory_margin_score": regulatory_margin_score(burnup_value, baseline),
    }


def fuel_reliability_penalty(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
) -> float:
    """Return a 0-1 screening penalty that begins above 55 GWd/MTU.

    It increases linearly to 1 at the study's 65 GWd/MTU upper bound. It is not
    a fuel qualification limit or an empirical failure probability.
    """
    burnup_value = _validate_burnup(burnup)
    penalty_span = max(
        1.0,
        max(DEFAULT_BURNUP_VALUES) - baseline.reliability_threshold_gwd_mtu,
    )
    return min(
        1.0,
        max(
            0.0,
            (burnup_value - baseline.reliability_threshold_gwd_mtu) / penalty_span,
        ),
    )


def cladding_degradation_score(burnup: float) -> float:
    """Return a heuristic 0-1 Zircaloy-2 degradation penalty over the study range.

    The quadratic proxy is a ranking device only; it is not a corrosion,
    hydriding, oxide-thickness, or cladding-strain model.
    """
    burnup_value = _validate_burnup(burnup)
    lower, upper = min(DEFAULT_BURNUP_VALUES), max(DEFAULT_BURNUP_VALUES)
    normalized = min(1.0, max(0.0, (burnup_value - lower) / (upper - lower)))
    return normalized**2


def regulatory_margin_score(
    burnup: float,
    baseline: BWRX300Baseline = BASELINE,
) -> float:
    """Score proximity to the 50 GWd/MTU reference point on a 0-1 scale."""
    burnup_value = _validate_burnup(burnup)
    margin_span = max(
        baseline.core_discharge_burnup_reference - min(DEFAULT_BURNUP_VALUES),
        max(DEFAULT_BURNUP_VALUES) - baseline.core_discharge_burnup_reference,
    )
    distance = abs(burnup_value - baseline.core_discharge_burnup_reference)
    return max(0.0, 1.0 - distance / margin_span)


def _normalize(values: pd.Series) -> pd.Series:
    """Min-max normalize a metric, returning zeros when it is constant."""
    spread = values.max() - values.min()
    if spread == 0.0:
        return pd.Series(0.0, index=values.index)
    return (values - values.min()) / spread


def run_burnup_sweep(
    burnup_values: Sequence[float] = DEFAULT_BURNUP_VALUES,
    baseline: BWRX300Baseline = BASELINE,
) -> pd.DataFrame:
    """Calculate cycle, reload, utilization, reliability, and cost metrics."""
    if len(burnup_values) == 0:
        raise ValueError("burnup_values must contain at least one value.")
    _validate_baseline(baseline)

    rows = [calculate_metrics(burnup, baseline) for burnup in burnup_values]
    results = pd.DataFrame(rows)
    results["normalized_burnup"] = _normalize(results["burnup_gwd_mtu"])
    results["normalized_cycle_length"] = _normalize(
        results["cycle_length_months"]
    )
    results["economic_score"] = 1.0 - _normalize(results["cost_per_mwh_usd"])
    reliability_factor = 1.0 - results["fuel_reliability_penalty"]
    cladding_factor = 1.0 - results["cladding_degradation_score"]
    results["fuel_utilization_score"] = (
        results["normalized_burnup"] * reliability_factor * cladding_factor
    )
    results["cycle_length_score"] = results["normalized_cycle_length"]
    results["safety_margin_score"] = (
        results["regulatory_margin_score"] * reliability_factor * cladding_factor
    )
    results["composite_score"] = sum(
        weight * results[metric]
        for metric, weight in SCORE_WEIGHTS.items()
    )
    return results


def find_optimum_burnup(results: pd.DataFrame) -> dict[str, pd.Series | str]:
    """Find the economic and balanced optima and a near-optimal burnup range."""
    required = {"burnup_gwd_mtu", "cost_per_mwh_usd", "composite_score"}
    missing = required.difference(results.columns)
    if missing:
        raise ValueError(f"Results are missing columns: {sorted(missing)}")
    if results.empty:
        raise ValueError("Cannot optimize an empty results DataFrame.")

    economic = results.loc[results["cost_per_mwh_usd"].idxmin()]
    balanced = results.loc[results["composite_score"].idxmax()]
    score_cutoff = results["composite_score"].max() * RECOMMENDATION_SCORE_FRACTION
    recommended = results.loc[results["composite_score"] >= score_cutoff]
    lower = recommended["burnup_gwd_mtu"].min()
    upper = recommended["burnup_gwd_mtu"].max()
    recommended_range = (
        f"{lower:g} GWd/MTU"
        if lower == upper
        else f"{lower:g}-{upper:g} GWd/MTU"
    )
    return {
        "economic": economic,
        "balanced": balanced,
        "recommended_range": recommended_range,
    }


def plot_results(results: pd.DataFrame) -> dict[str, plt.Figure]:
    """Create requested burnup tradeoff plots and a utilization-cost Pareto plot."""
    plot_specs = (
        ("cycle_length_months", "Burnup vs Cycle Length", "Cycle Length (months)"),
        ("bundles_replaced", "Burnup vs Bundles Replaced Per Cycle", "Bundles"),
        ("cost_per_mwh_usd", "Burnup vs Cost per MWh", "Cost ($/MWh)"),
        ("composite_score", "Burnup vs Composite Optimization Score", "Score"),
    )
    figures: dict[str, plt.Figure] = {}
    for metric, title, y_label in plot_specs:
        figure, axis = plt.subplots()
        axis.plot(results["burnup_gwd_mtu"], results[metric], marker="o")
        axis.set_title(title)
        axis.set_xlabel("Burnup (GWd/MTU)")
        axis.set_ylabel(y_label)
        axis.grid(True, alpha=0.3)
        figure.tight_layout()
        figures[metric] = figure

    pareto, axis = plt.subplots()
    axis.scatter(
        results["fuel_utilization_mwh_e_per_kg_u"],
        results["cost_per_mwh_usd"],
    )
    for row in results.itertuples(index=False):
        axis.annotate(
            f"{row.burnup_gwd_mtu:g}",
            (row.fuel_utilization_mwh_e_per_kg_u, row.cost_per_mwh_usd),
            xytext=(5, 5),
            textcoords="offset points",
        )
    axis.set_title("Fuel Utilization vs Cost per MWh")
    axis.set_xlabel("Fuel Utilization (MWh electric/kgU)")
    axis.set_ylabel("Cost ($/MWh)")
    axis.grid(True, alpha=0.3)
    pareto.tight_layout()
    figures["pareto"] = pareto
    return figures


def main() -> None:
    """Run the study, export results, and print the recommendation."""
    results = run_burnup_sweep()
    optima = find_optimum_burnup(results)
    results.to_csv("burnup_study_results.csv", index=False)

    economic = optima["economic"]
    balanced = optima["balanced"]
    assert isinstance(economic, pd.Series)
    assert isinstance(balanced, pd.Series)
    print(f"Reference Design Burnup: {BASELINE.core_discharge_burnup_reference:g} GWd/MTU")
    print(
        f"Economic Optimum: {economic['burnup_gwd_mtu']:g} GWd/MTU "
        f"(${economic['cost_per_mwh_usd']:.2f}/MWh)"
    )
    print(
        f"Balanced Optimum: {balanced['burnup_gwd_mtu']:g} GWd/MTU "
        f"(score {balanced['composite_score']:.3f}, "
        f"{balanced['cycle_length_months']:.1f}-month cycle, "
        f"{balanced['bundles_replaced']:.1f} bundles/cycle)"
    )
    print(f"Recommended Operating Range: {optima['recommended_range']}")
    print("\nBurnup tradeoff summary:")
    print(
        results[
            [
                "burnup_gwd_mtu",
                "cycle_length_months",
                "bundles_replaced",
                "outages_per_year",
                "cost_per_mwh_usd",
                "composite_score",
            ]
        ].to_string(index=False, float_format=lambda value: f"{value:.2f}")
    )
    print("\nSaved results to burnup_study_results.csv")
    plot_results(results)
    plt.show()


if __name__ == "__main__":
    main()