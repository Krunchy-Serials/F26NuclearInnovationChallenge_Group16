"""NSGA-II optimization and comparison of estimated BWR startup procedures.

Without STARTUP_SIMULATOR, results use an explicitly illustrative estimate model
based on qualitative, literature-informed trends. They are not reactor
simulations or predictive correlations. A configured validated simulator can
replace the estimates through the existing adapter interface.
"""

from __future__ import annotations

import importlib
import json
import math
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize


DEFAULT_HOLD_SCHEDULES = ((), (25,), (25, 50), (25, 50, 75))
OBJECTIVES = (
    "startup_time_minutes",
    "flashing_instability_risk",
    "density_wave_oscillation_risk",
    "geysering_risk",
    "thermal_stress",
    "startup_cost",
)
MetricRunner = Callable[[dict[str, Any]], Mapping[str, Any]]
RISK_COLUMNS = {
    "Flashing": "flashing_instability_risk",
    "Density wave oscillation": "density_wave_oscillation_risk",
    "Geysering": "geysering_risk",
}


@dataclass(frozen=True)
class HoldPoint:
    """A requested power hold, with power in percent and duration in minutes."""

    power_percent: int
    duration_minutes: float


@dataclass(frozen=True)
class StartupProcedure:
    """Candidate startup inputs passed unchanged to an external simulator."""

    power_ramp_rate: float
    pressure_ramp_rate: float
    boiling_initiation_pressure: float
    inlet_subcooling: float
    hold_schedule: tuple[HoldPoint, ...]

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly payload for external simulation drivers."""
        return {
            "power_ramp_rate": self.power_ramp_rate,
            "pressure_ramp_rate": self.pressure_ramp_rate,
            "boiling_initiation_pressure": self.boiling_initiation_pressure,
            "inlet_subcooling": self.inlet_subcooling,
            "hold_schedule": [asdict(point) for point in self.hold_schedule],
        }


@dataclass(frozen=True)
class BaselineStartupProcedure(StartupProcedure):
    """Reference procedure used for the literature-informed comparison."""

    power_ramp_rate: float = 2.5
    pressure_ramp_rate: float = 0.8
    boiling_initiation_pressure: float = 2.0
    inlet_subcooling: float = 10.0
    hold_schedule: tuple[HoldPoint, ...] = ()


@dataclass(frozen=True)
class OptimizedStartupProcedure(StartupProcedure):
    """Procedure selected from the Pareto front for comparison."""

    @classmethod
    def from_candidate(cls, candidate: Mapping[str, Any]) -> OptimizedStartupProcedure:
        """Build a procedure from a Pareto-result row."""
        schedule_data = candidate["hold_schedule"]
        if isinstance(schedule_data, str):
            schedule_data = json.loads(schedule_data)
        return cls(
            power_ramp_rate=float(candidate["power_ramp_rate"]),
            pressure_ramp_rate=float(candidate["pressure_ramp_rate"]),
            boiling_initiation_pressure=float(
                candidate["boiling_initiation_pressure"]
            ),
            inlet_subcooling=float(candidate["inlet_subcooling"]),
            hold_schedule=tuple(
                HoldPoint(
                    power_percent=int(point["power_percent"]),
                    duration_minutes=float(point["duration_minutes"]),
                )
                for point in schedule_data
            ),
        )


@dataclass(frozen=True)
class SimulationMetrics:
    """Metrics supplied by simulator post-processing, not calculated here.

    Risk values must already be expressed on a backend-defined 0-100 scale.
    Thermal stress and startup cost must use consistent units across candidates.
    """

    startup_time_minutes: float
    flashing_instability_risk: float
    density_wave_oscillation_risk: float
    geysering_risk: float
    thermal_stress: float
    startup_cost: float

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> SimulationMetrics:
        """Validate the required simulator output contract."""
        missing = set(OBJECTIVES).difference(values)
        if missing:
            raise ValueError(f"Simulator output is missing metrics: {sorted(missing)}")

        metrics = cls(**{name: float(values[name]) for name in OBJECTIVES})
        for name, value in asdict(metrics).items():
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(
                    f"Simulator metric {name} must be finite and nonnegative."
                )
        for name in OBJECTIVES[1:4]:
            if getattr(metrics, name) > 100.0:
                raise ValueError(f"Simulator risk {name} must use a 0-100 scale.")
        return metrics

    def objective_vector(self) -> list[float]:
        """Return minimized objectives in the optimizer's declared order."""
        return [float(getattr(self, name)) for name in OBJECTIVES]


class StartupSimulator(Protocol):
    """Interface implemented by a transient solver or post-processing adapter."""

    def evaluate(self, procedure: StartupProcedure) -> SimulationMetrics:
        """Run one procedure and return validated simulator outputs."""
        ...


class LiteratureBasedEstimateSimulator:
    """Illustrative sensitivity model for demonstrating the optimization flow.

    The factors below implement qualitative relationships, not literature-
    derived correlations. Replace this model with validated MOOSE THM or
    OpenFOAM/GeN-Foam post-processing when those integrations are available.
    """

    def evaluate(self, procedure: StartupProcedure) -> SimulationMetrics:
        hold_count = len(procedure.hold_schedule)
        hold_minutes = sum(
            point.duration_minutes for point in procedure.hold_schedule
        )
        # Demonstration sensitivities are intentionally transparent and bounded.
        startup_time = (
            150.0 / procedure.power_ramp_rate
            + (procedure.inlet_subcooling - 5.0) * 0.3
            + hold_minutes
        )
        # Boiling initiation pressure is only a demonstration proxy for pressure.
        flashing_risk = (
            50.0
            + (procedure.power_ramp_rate - 2.5) * 10.0
            + (2.0 - procedure.boiling_initiation_pressure) * 5.0
            - (procedure.inlet_subcooling - 10.0) * 0.6
            - hold_count * 3.0
            - hold_minutes * 0.08
        )
        dwo_risk = (
            45.0
            + (procedure.power_ramp_rate - 2.5) * 10.0
            - hold_count * 4.0
            - hold_minutes * 0.05
        )
        geysering_risk = (
            50.0
            + (2.0 - procedure.boiling_initiation_pressure) * 5.0
            - hold_count * 2.0
            - hold_minutes * 0.03
        )
        thermal_stress = 50.0 + (procedure.pressure_ramp_rate - 0.8) * 20.0
        # A relative cost index only; no currency or plant-cost model is implied.
        startup_cost = startup_time * 1_000.0 + hold_count * 250.0
        return SimulationMetrics.from_mapping(
            {
                "startup_time_minutes": startup_time,
                "flashing_instability_risk": min(100.0, max(0.0, flashing_risk)),
                "density_wave_oscillation_risk": min(100.0, max(0.0, dwo_risk)),
                "geysering_risk": min(100.0, max(0.0, geysering_risk)),
                "thermal_stress": max(0.0, thermal_stress),
                "startup_cost": startup_cost,
            }
        )


class ReactorPhysicsProvider(Protocol):
    """Interface for optional neutronics inputs such as OpenMC results."""

    def evaluate(self, procedure: StartupProcedure) -> Mapping[str, Any]:
        """Return physics fields consumed by a coupled thermal-hydraulics run."""
        ...


class MOOSETHMAdapter:
    """Bridge a project-specific MOOSE THM transient runner to the optimizer."""

    def __init__(self, transient_runner: MetricRunner) -> None:
        self.transient_runner = transient_runner

    def evaluate(self, procedure: StartupProcedure) -> SimulationMetrics:
        """Run MOOSE and adapt its post-processed metrics to the output contract."""
        outputs = self.transient_runner(procedure.to_payload())
        return SimulationMetrics.from_mapping(outputs)


class OpenFOAMGeNFoamAdapter:
    """Bridge a project-specific OpenFOAM/GeN-Foam transient runner."""

    def __init__(self, transient_runner: MetricRunner) -> None:
        self.transient_runner = transient_runner

    def evaluate(self, procedure: StartupProcedure) -> SimulationMetrics:
        """Run the external solver and validate its post-processed metrics."""
        outputs = self.transient_runner(procedure.to_payload())
        return SimulationMetrics.from_mapping(outputs)


class OpenMCPhysicsAdapter:
    """Expose OpenMC results as inputs to a coupled thermal-hydraulics runner."""

    def __init__(self, physics_runner: MetricRunner) -> None:
        self.physics_runner = physics_runner

    def evaluate(self, procedure: StartupProcedure) -> Mapping[str, Any]:
        """Run OpenMC and return fields such as power shape or reactivity data."""
        return self.physics_runner(procedure.to_payload())


class CoupledStartupSimulator:
    """Pass optional OpenMC results into an external MOOSE or GeN-Foam runner."""

    def __init__(
        self,
        coupled_runner: Callable[
            [dict[str, Any], Mapping[str, Mapping[str, Any]]], Mapping[str, Any]
        ],
        physics_providers: Mapping[str, ReactorPhysicsProvider],
    ) -> None:
        self.coupled_runner = coupled_runner
        self.physics_providers = physics_providers

    def evaluate(self, procedure: StartupProcedure) -> SimulationMetrics:
        """Run physics providers, then validate coupled transient outputs."""
        physics = {
            name: provider.evaluate(procedure)
            for name, provider in self.physics_providers.items()
        }
        outputs = self.coupled_runner(procedure.to_payload(), physics)
        return SimulationMetrics.from_mapping(outputs)


@dataclass(frozen=True)
class SearchSpace:
    """Design bounds and discrete hold patterns for NSGA-II candidates."""

    power_ramp_bounds: tuple[float, float] = (0.5, 3.0)
    pressure_ramp_bounds: tuple[float, float] = (0.1, 1.0)
    boiling_pressure_bounds: tuple[float, float] = (1.0, 7.0)
    inlet_subcooling_bounds: tuple[float, float] = (5.0, 50.0)
    hold_duration_bounds: tuple[float, float] = (0.0, 60.0)
    hold_schedules: tuple[tuple[int, ...], ...] = DEFAULT_HOLD_SCHEDULES

    def decode(self, vector: np.ndarray) -> StartupProcedure:
        """Convert a search vector into settings and a discrete hold schedule."""
        schedule_index = int(
            np.clip(np.rint(vector[4]), 0, len(self.hold_schedules) - 1)
        )
        duration = float(vector[5])
        schedule = tuple(
            HoldPoint(level, duration)
            for level in self.hold_schedules[schedule_index]
        )
        if not schedule:
            duration = 0.0
        return StartupProcedure(
            power_ramp_rate=float(vector[0]),
            pressure_ramp_rate=float(vector[1]),
            boiling_initiation_pressure=float(vector[2]),
            inlet_subcooling=float(vector[3]),
            hold_schedule=tuple(
                HoldPoint(point.power_percent, duration) for point in schedule
            ),
        )

    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Return lower and upper bounds in the encoded decision-variable order."""
        lower = np.array(
            [
                self.power_ramp_bounds[0],
                self.pressure_ramp_bounds[0],
                self.boiling_pressure_bounds[0],
                self.inlet_subcooling_bounds[0],
                0.0,
                self.hold_duration_bounds[0],
            ]
        )
        upper = np.array(
            [
                self.power_ramp_bounds[1],
                self.pressure_ramp_bounds[1],
                self.boiling_pressure_bounds[1],
                self.inlet_subcooling_bounds[1],
                float(len(self.hold_schedules) - 1),
                self.hold_duration_bounds[1],
            ]
        )
        return lower, upper


class _StartupProblem(ElementwiseProblem):
    """Pymoo problem delegating every evaluation to the configured backend."""

    def __init__(self, simulator: StartupSimulator, search_space: SearchSpace) -> None:
        lower, upper = search_space.bounds()
        super().__init__(n_var=6, n_obj=len(OBJECTIVES), xl=lower, xu=upper)
        self.simulator = simulator
        self.search_space = search_space
        self.records: dict[tuple[Any, ...], dict[str, Any]] = {}

    @staticmethod
    def _key(procedure: StartupProcedure) -> tuple[Any, ...]:
        return (
            round(procedure.power_ramp_rate, 8),
            round(procedure.pressure_ramp_rate, 8),
            round(procedure.boiling_initiation_pressure, 8),
            round(procedure.inlet_subcooling, 8),
            tuple(
                (point.power_percent, round(point.duration_minutes, 8))
                for point in procedure.hold_schedule
            ),
        )

    def _evaluate(
        self,
        vector: np.ndarray,
        out: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        procedure = self.search_space.decode(vector)
        key = self._key(procedure)
        if key not in self.records:
            metrics = self.simulator.evaluate(procedure)
            self.records[key] = {
                **procedure.to_payload(),
                **asdict(metrics),
                "_decision_key": key,
                "candidate_id": len(self.records),
            }
        out["F"] = [float(self.records[key][name]) for name in OBJECTIVES]


def _normalize_objectives(values: pd.DataFrame) -> pd.DataFrame:
    """Normalize objectives only for decision-support ranking."""
    normalized = pd.DataFrame(index=values.index)
    for name in OBJECTIVES:
        span = values[name].max() - values[name].min()
        normalized[name] = (
            0.0 if span == 0.0 else (values[name] - values[name].min()) / span
        )
    return normalized


def rank_pareto_candidates(
    results: pd.DataFrame,
    weights: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Rank Pareto candidates by normalized compromise, separate from simulation.

    Equal objective weights are the default. This is a decision preference, not
    an instability calculation or a claim that the top row is inherently safest.
    """
    if results.empty:
        raise ValueError("Cannot rank an empty result set.")
    weights = weights or {name: 1.0 for name in OBJECTIVES}
    if set(weights) != set(OBJECTIVES):
        raise ValueError("Ranking weights must specify every objective exactly once.")
    if any(value < 0.0 or not math.isfinite(value) for value in weights.values()):
        raise ValueError("Ranking weights must be finite and nonnegative.")
    weight_total = sum(weights.values())
    if weight_total <= 0.0:
        raise ValueError("At least one ranking weight must be positive.")

    ranked = results.loc[results["is_pareto"]].copy()
    if ranked.empty:
        ranked = results.copy()
    normalized = _normalize_objectives(ranked)
    weighted_loss = sum(weights[name] * normalized[name] for name in OBJECTIVES)
    ranked["decision_support_score"] = 1.0 - weighted_loss / weight_total
    return ranked.sort_values(
        "decision_support_score", ascending=False
    ).reset_index(drop=True)


def run_parameter_sweep(
    simulator: StartupSimulator,
    *,
    population_size: int = 100,
    generations: int = 20,
    seed: int = 20261003,
    search_space: SearchSpace = SearchSpace(),
) -> pd.DataFrame:
    """Run NSGA-II and return unique simulator evaluations with Pareto flags."""
    if population_size < 4 or generations < 1:
        raise ValueError("NSGA-II needs population_size >= 4 and generations >= 1.")
    problem = _StartupProblem(simulator, search_space)
    result = minimize(
        problem,
        NSGA2(pop_size=population_size, eliminate_duplicates=True),
        termination=("n_gen", generations),
        seed=seed,
        verbose=False,
    )
    if result.X is None:
        raise RuntimeError("NSGA-II returned no candidate solutions.")

    pareto_keys = {
        problem._key(search_space.decode(vector))
        for vector in np.atleast_2d(result.X)
    }
    records = []
    for key, record in problem.records.items():
        row = {name: value for name, value in record.items() if name != "_decision_key"}
        row["hold_schedule"] = json.dumps(record["hold_schedule"])
        row["is_pareto"] = key in pareto_keys
        records.append(row)
    dataframe = pd.DataFrame(records)
    pareto_ranked = rank_pareto_candidates(dataframe)
    scores = pareto_ranked.set_index("candidate_id")["decision_support_score"]
    dataframe["decision_support_score"] = dataframe["candidate_id"].map(scores)
    return dataframe.sort_values(
        ["is_pareto", "decision_support_score"],
        ascending=[False, False],
        na_position="last",
    ).reset_index(drop=True)


def find_best_procedure(results: pd.DataFrame) -> dict[str, pd.Series]:
    """Return compromise, fastest, lowest-cost, and per-risk best procedures."""
    if results.empty:
        raise ValueError("Cannot choose a procedure from an empty result set.")
    ranked = rank_pareto_candidates(results)
    return {
        "overall": ranked.iloc[0],
        "fastest": results.loc[results["startup_time_minutes"].idxmin()],
        "lowest_cost": results.loc[results["startup_cost"].idxmin()],
        "lowest_flashing_risk": results.loc[
            results["flashing_instability_risk"].idxmin()
        ],
        "lowest_dwo_risk": results.loc[
            results["density_wave_oscillation_risk"].idxmin()
        ],
        "lowest_geysering_risk": results.loc[results["geysering_risk"].idxmin()],
    }


def _risk_long_form(results: pd.DataFrame) -> pd.DataFrame:
    """Expand independent risk outputs without combining their values."""
    return pd.concat(
        [
            results.assign(risk_type=label, instability_risk=results[column])
            for label, column in RISK_COLUMNS.items()
        ],
        ignore_index=True,
    )


def create_pareto_plots(
    results: pd.DataFrame,
    output_directory: str | Path = "results",
) -> dict[str, plt.Figure]:
    """Save three requested tradeoff plots and interactive Plotly versions."""
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    pareto = results.loc[results["is_pareto"]].copy()
    if pareto.empty:
        pareto = results.copy()
    risks = _risk_long_form(results)
    risk_front = _risk_long_form(pareto)
    figures: dict[str, plt.Figure] = {}

    figure, axis = plt.subplots()
    for name, group in risks.groupby("risk_type", sort=False):
        axis.scatter(
            group["startup_time_minutes"],
            group["instability_risk"],
            s=18,
            alpha=0.2,
            label=f"{name} (evaluated)",
        )
    for name, group in risk_front.groupby("risk_type", sort=False):
        axis.scatter(
            group["startup_time_minutes"],
            group["instability_risk"],
            s=36,
            alpha=0.9,
            label=f"{name} (Pareto)",
        )
    axis.set(
        title="Startup Time vs Instability Risks",
        xlabel="Startup time (min)",
        ylabel="Backend risk output (0-100)",
    )
    axis.grid(True, alpha=0.25)
    axis.legend(fontsize="small")
    figures["time_vs_risk"] = figure

    figure, axis = plt.subplots()
    axis.scatter(
        results["startup_time_minutes"],
        results["startup_cost"],
        alpha=0.25,
        label="Evaluated",
    )
    axis.scatter(
        pareto["startup_time_minutes"],
        pareto["startup_cost"],
        s=36,
        label="Pareto",
    )
    axis.set(
        title="Startup Time vs Cost",
        xlabel="Startup time (min)",
        ylabel="Backend startup cost",
    )
    axis.grid(True, alpha=0.25)
    axis.legend()
    figures["time_vs_cost"] = figure

    figure, axis = plt.subplots()
    for name, group in risks.groupby("risk_type", sort=False):
        axis.scatter(
            group["startup_cost"],
            group["instability_risk"],
            s=18,
            alpha=0.2,
            label=name,
        )
    axis.set(
        title="Cost vs Instability Risks",
        xlabel="Backend startup cost",
        ylabel="Backend risk output (0-100)",
    )
    axis.grid(True, alpha=0.25)
    axis.legend()
    figures["cost_vs_risk"] = figure

    for name, plot in figures.items():
        plot.tight_layout()
        plot.savefig(output_path / f"{name}.png", dpi=160)

    px.scatter(
        risks,
        x="startup_time_minutes",
        y="instability_risk",
        color="risk_type",
        symbol="is_pareto",
        hover_data=["startup_cost", "thermal_stress", "power_ramp_rate"],
        title="Startup Time vs Backend Instability Outputs",
    ).write_html(output_path / "time_vs_risk.html")
    px.scatter(
        results,
        x="startup_time_minutes",
        y="startup_cost",
        color="is_pareto",
        title="Startup Time vs Cost",
    ).write_html(output_path / "time_vs_cost.html")
    px.scatter(
        risks,
        x="startup_cost",
        y="instability_risk",
        color="risk_type",
        symbol="is_pareto",
        title="Cost vs Backend Instability Outputs",
    ).write_html(output_path / "cost_vs_risk.html")
    return figures


def generate_report(results: pd.DataFrame) -> str:
    """Summarize the Pareto compromise and preserve each risk metric separately."""
    ranked = rank_pareto_candidates(results)
    best = ranked.iloc[0]
    hold_schedule = json.loads(best["hold_schedule"])
    lines = [
        "Recommended Pareto Compromise",
        f"Power ramp rate: {best['power_ramp_rate']:.3f} %FP/min",
        f"Pressure ramp rate: {best['pressure_ramp_rate']:.3f} MPa/min",
        f"Boiling initiation pressure: {best['boiling_initiation_pressure']:.3f} MPa",
        f"Inlet subcooling: {best['inlet_subcooling']:.2f} C",
        f"Hold point schedule: {hold_schedule}",
        f"Startup time: {best['startup_time_minutes']:.2f} minutes",
        f"Flashing risk: {best['flashing_instability_risk']:.2f}/100",
        f"Density-wave risk: {best['density_wave_oscillation_risk']:.2f}/100",
        f"Geysering risk: {best['geysering_risk']:.2f}/100",
        f"Thermal stress: {best['thermal_stress']:.3f}",
        f"Startup cost: {best['startup_cost']:.3f}",
        f"Decision-support score: {best['decision_support_score']:.4f}",
        "",
        "Top Pareto Candidates",
    ]
    for rank, (_, candidate) in enumerate(ranked.head(5).iterrows(), start=1):
        lines.append(
            f"{rank}. score={candidate['decision_support_score']:.4f}, "
            f"time={candidate['startup_time_minutes']:.2f} min, "
            f"cost={candidate['startup_cost']:.3f}, "
            f"risks=(flashing {candidate['flashing_instability_risk']:.2f}, "
            f"DWO {candidate['density_wave_oscillation_risk']:.2f}, "
            f"geysering {candidate['geysering_risk']:.2f})"
        )
    lines.extend(
        [
            "",
        "The selected candidate is a normalized compromise across the six backend "
        "outputs. Risk types remain separate; this optimizer adds no combined "
        "instability equation.",
        "",
        "This recommendation depends on the configured backend or estimate "
        "model and its assumptions. It is not a plant operating procedure.",
        "When the built-in estimate model is active, these are illustrative "
        "literature-informed estimates, not predictive reactor simulations.",
        ]
    )
    return "\n".join(lines)


def generate_improvement_report(
    results: pd.DataFrame,
    simulator: StartupSimulator | None = None,
    output_directory: str | Path = "results/improvements",
) -> str:
    """Compare the fixed baseline against the top-ranked Pareto candidate.

    The comparison and its four bar charts are written to output_directory.
    Percentage change is (baseline - optimized) / baseline; negative time or
    cost percentages are explicitly reported as a performance worsening.
    """
    if results.empty:
        raise ValueError("Cannot compare procedures from an empty result set.")

    simulator = simulator or LiteratureBasedEstimateSimulator()
    ranked = rank_pareto_candidates(results)
    candidate = ranked.iloc[0]
    baseline = BaselineStartupProcedure()
    optimized = OptimizedStartupProcedure.from_candidate(candidate)
    baseline_metrics = simulator.evaluate(baseline)
    optimized_metrics = SimulationMetrics.from_mapping(candidate.to_dict())

    metrics = (
        ("Flashing Instability Risk", "flashing_instability_risk"),
        ("Density Wave Oscillation Risk", "density_wave_oscillation_risk"),
        ("Geysering Risk", "geysering_risk"),
        ("Thermal Stress", "thermal_stress"),
        ("Startup Time", "startup_time_minutes"),
        ("Startup Cost", "startup_cost"),
    )
    rows = []
    for label, name in metrics:
        baseline_value = float(getattr(baseline_metrics, name))
        optimized_value = float(getattr(optimized_metrics, name))
        percent = (
            (baseline_value - optimized_value) / baseline_value * 100.0
            if baseline_value != 0.0
            else None
        )
        status = ""
        if name in {"startup_time_minutes", "startup_cost"}:
            if percent is None:
                status = " (comparison unavailable)"
            elif percent > 0.0:
                status = " (improved)"
            elif percent < 0.0:
                status = " (worsened)"
            else:
                status = " (unchanged)"
        rows.append(
            (
                label,
                baseline_value,
                optimized_value,
                f"{percent:+.2f}%{status}" if percent is not None else "N/A (baseline 0)",
            )
        )

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    is_estimate = isinstance(simulator, LiteratureBasedEstimateSimulator)
    if is_estimate:
        qualification = [
            "Literature-based engineering estimates used to demonstrate the "
            "startup optimization framework.",
            "",
            "These are illustrative, qualitative-trend estimates—not predictive "
            "reactor simulations, validated literature correlations, or "
            "operating guidance. Sensitivity factors in "
            "LiteratureBasedEstimateSimulator are demonstration assumptions, "
            "not values calibrated against BWRX-300 data.",
        ]
    else:
        qualification = [
            "Startup procedure comparison using the configured simulator backend.",
            "",
            "These outputs are simulator results, not validated plant-operating "
            "guidance; validate the backend and its applicability independently.",
        ]
    procedure_lines = [
        *qualification,
        "",
        "Baseline Procedure",
        f"Power ramp rate: {baseline.power_ramp_rate:.3f} %FP/min",
        f"Pressure ramp rate: {baseline.pressure_ramp_rate:.3f} MPa/min",
        f"Boiling initiation pressure: "
        f"{baseline.boiling_initiation_pressure:.3f} MPa",
        f"Inlet subcooling: {baseline.inlet_subcooling:.2f} C",
        f"Hold schedule: {baseline.to_payload()['hold_schedule']}",
        "",
        "Optimized Procedure (selected from Pareto-optimal solutions)",
        f"Power ramp rate: {optimized.power_ramp_rate:.3f} %FP/min",
        f"Pressure ramp rate: {optimized.pressure_ramp_rate:.3f} MPa/min",
        f"Boiling initiation pressure: "
        f"{optimized.boiling_initiation_pressure:.3f} MPa",
        f"Inlet subcooling: {optimized.inlet_subcooling:.2f} C",
        f"Hold schedule: {optimized.to_payload()['hold_schedule']}",
        "",
        "Improvement Table",
        f"{'Metric':<34} {'Baseline':>14} {'Optimized':>14} "
        f"{'Percent Improvement':>25}",
        "-" * 91,
    ]
    for label, baseline_value, optimized_value, percent in rows:
        procedure_lines.append(
            f"{label:<34} {baseline_value:>14.3f} "
            f"{optimized_value:>14.3f} {percent:>25}"
        )

    risk_improvements = [
        (baseline_value - optimized_value) / baseline_value * 100.0
        for _, name in metrics[:3]
        for baseline_value, optimized_value in [
            (
                float(getattr(baseline_metrics, name)),
                float(getattr(optimized_metrics, name)),
            )
        ]
        if baseline_value > 0.0
    ]
    time_change = next(
        float(getattr(optimized_metrics, name))
        - float(getattr(baseline_metrics, name))
        for _, name in metrics
        if name == "startup_time_minutes"
    )
    if time_change > 0.0 and risk_improvements and all(
        improvement > 0.0 for improvement in risk_improvements
    ):
        duration_description = (
            "modest"
            if time_change <= 0.2 * baseline_metrics.startup_time_minutes
            else "substantial"
        )
        interpretation = (
            f"The optimized startup procedure accepts a {duration_description} "
            "increase in startup duration in exchange for reductions in "
            "flashing instability risk, density-wave oscillation risk, and "
            "geysering susceptibility."
        )
    else:
        interpretation = (
            "The optimized procedure represents a normalized multi-objective "
            "compromise. Review the table for the measured estimated trade-offs; "
            "the ranking does not imply that the procedure is inherently safer."
        )
    procedure_lines.extend(
        [
            "",
            "Engineering Interpretation",
            interpretation,
            "Risk values are separate illustrative indices on a 0-100 scale. "
            "Startup cost is a relative index, not a currency estimate.",
            "Future validated MOOSE THM or OpenFOAM/GeN-Foam integrations can "
            "replace the estimate model through STARTUP_SIMULATOR.",
        ]
    )
    report = "\n".join(procedure_lines)
    (output_path / "improvement_summary.txt").write_text(
        report + "\n",
        encoding="utf-8",
    )

    chart_specs = (
        (
            "flashing_risk_comparison.png",
            "Baseline vs Optimized Flashing Risk",
            baseline_metrics.flashing_instability_risk,
            optimized_metrics.flashing_instability_risk,
        ),
        (
            "dwo_risk_comparison.png",
            "Baseline vs Optimized DWO Risk",
            baseline_metrics.density_wave_oscillation_risk,
            optimized_metrics.density_wave_oscillation_risk,
        ),
        (
            "geysering_risk_comparison.png",
            "Baseline vs Optimized Geysering Risk",
            baseline_metrics.geysering_risk,
            optimized_metrics.geysering_risk,
        ),
        (
            "thermal_stress_comparison.png",
            "Baseline vs Optimized Thermal Stress",
            baseline_metrics.thermal_stress,
            optimized_metrics.thermal_stress,
        ),
    )
    for filename, title, baseline_value, optimized_value in chart_specs:
        figure, axis = plt.subplots()
        axis.bar(
            ["Baseline", "Optimized"],
            [baseline_value, optimized_value],
            color=["#6c757d", "#2a9d8f"],
        )
        axis.set(
            title=title,
            ylabel=(
                "Illustrative estimate"
                if is_estimate
                else "Configured simulator output"
            ),
        )
        axis.grid(axis="y", alpha=0.25)
        figure.tight_layout()
        figure.savefig(output_path / filename, dpi=160)
        plt.close(figure)
    return report


def load_simulator_from_environment() -> StartupSimulator:
    """Load an external simulator, or use the labeled estimate model by default."""
    factory_path = os.environ.get("STARTUP_SIMULATOR")
    if not factory_path:
        return LiteratureBasedEstimateSimulator()
    if ":" not in factory_path:
        raise ValueError(
            "STARTUP_SIMULATOR must use package.module:create_simulator format."
        )
    module_name, factory_name = factory_path.split(":", maxsplit=1)
    factory = getattr(importlib.import_module(module_name), factory_name)
    return factory()


def main() -> None:
    """Run NSGA-II with the configured external simulator and export results."""
    simulator = load_simulator_from_environment()
    results = run_parameter_sweep(simulator)
    results.to_csv("startup_optimization_results.csv", index=False)
    create_pareto_plots(results, "results")
    report = generate_report(results)
    Path("results/startup_optimization_report.txt").write_text(
        report + "\n",
        encoding="utf-8",
    )
    improvement_report = generate_improvement_report(results, simulator)
    print(f"Recorded {len(results):,} unique simulator evaluations.")
    print(f"Pareto candidates: {int(results['is_pareto'].sum()):,}")
    print(
        "Saved startup_optimization_results.csv, Pareto plots, and improvement "
        "comparison under results/."
    )
    print("\n" + report)
    print("\n" + improvement_report)


if __name__ == "__main__":
    main()
