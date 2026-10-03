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
from dataclasses import asdict, dataclass, replace
from enum import Enum
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
FLASHING_THRESHOLD_PRESSURE_MPA = 0.4
STABLE_TWO_PHASE_PRESSURE_MPA = 0.7
OBJECTIVES = (
    "startup_time_minutes",
    "flashing_margin",
    "density_wave_oscillation_index",
    "pressure_oscillation_index",
    "thermal_stress",
    "startup_cost",
)
MAXIMIZE_OBJECTIVES = frozenset({"flashing_margin"})
MetricRunner = Callable[[dict[str, Any]], Mapping[str, Any]]
STABILITY_COLUMNS = {
    "Flashing margin": "flashing_margin",
    "Density-wave oscillation index": "density_wave_oscillation_index",
    "Pressure oscillation index": "pressure_oscillation_index",
}


class StartupType(str, Enum):
    """Startup category with illustrative initial pressure and temperature."""

    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"


class PriorityMode(str, Enum):
    """Explicit decision modes used to rank startup profiles."""

    STABILITY = "stability-priority"
    SPEED = "speed-priority"
    COST = "cost-priority"


@dataclass(frozen=True)
class InitialConditions:
    pressure_mpa: float
    temperature_c: float


# Illustrative values for demo comparisons only; they are not BWRX-300 limits.
STARTUP_INITIAL_CONDITIONS = {
    StartupType.COLD: InitialConditions(pressure_mpa=0.1, temperature_c=20.0),
    StartupType.WARM: InitialConditions(pressure_mpa=0.7, temperature_c=120.0),
    StartupType.HOT: InitialConditions(pressure_mpa=2.0, temperature_c=200.0),
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
    startup_type: StartupType = StartupType.COLD

    @property
    def initial_conditions(self) -> InitialConditions:
        return STARTUP_INITIAL_CONDITIONS[self.startup_type]

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-friendly payload for external simulation drivers."""
        initial_conditions = self.initial_conditions
        return {
            "power_ramp_rate": self.power_ramp_rate,
            "pressure_ramp_rate": self.pressure_ramp_rate,
            "boiling_initiation_pressure": self.boiling_initiation_pressure,
            "inlet_subcooling": self.inlet_subcooling,
            "hold_schedule": [asdict(point) for point in self.hold_schedule],
            "startup_type": self.startup_type.value,
            "initial_pressure_mpa": initial_conditions.pressure_mpa,
            "initial_temperature_c": initial_conditions.temperature_c,
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
            startup_type=StartupType(candidate.get("startup_type", "COLD")),
        )


@dataclass(frozen=True)
class SimulationMetrics:
    """Metrics supplied by simulator post-processing, not calculated here.

    The estimate model uses higher flashing margin as better and minimizes the
    two indices and remaining objectives. Units and definitions for simulator
    outputs must be supplied by each backend.
    """

    startup_time_minutes: float
    flashing_margin: float
    density_wave_oscillation_index: float
    pressure_oscillation_index: float
    thermal_stress: float
    startup_cost: float
    lost_generation_index: float = 0.0
    operator_intervention_index: float = 0.0
    thermal_stress_penalty: float = 0.0

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> SimulationMetrics:
        """Validate the required simulator output contract."""
        component_names = (
            "lost_generation_index",
            "operator_intervention_index",
            "thermal_stress_penalty",
        )
        supplied_components = [name in values for name in component_names]
        if any(supplied_components) and not all(supplied_components):
            raise ValueError(
                "Simulator output must provide all startup-cost components or none."
            )
        missing = set(OBJECTIVES).difference(values)
        if all(supplied_components):
            missing.discard("startup_cost")
        if missing:
            raise ValueError(f"Simulator output is missing metrics: {sorted(missing)}")

        fields = {
            name: float(values[name])
            for name in OBJECTIVES
            if name in values
        }
        if all(supplied_components):
            components = {
                name: float(values[name]) for name in component_names
            }
            fields.update(components)
            fields["startup_cost"] = sum(components.values())
        metrics = cls(**fields)
        for name, value in asdict(metrics).items():
            if not math.isfinite(value) or (
                value < 0.0 and name not in MAXIMIZE_OBJECTIVES
            ):
                raise ValueError(
                    f"Simulator metric {name} must be finite and nonnegative."
                )
        return metrics

    def objective_vector(self) -> list[float]:
        """Return objectives in the optimizer's all-minimization form."""
        return [
            -float(getattr(self, name))
            if name in MAXIMIZE_OBJECTIVES
            else float(getattr(self, name))
            for name in OBJECTIVES
        ]


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
        initial = procedure.initial_conditions
        startup_time = (
            150.0 / procedure.power_ramp_rate
            + (procedure.inlet_subcooling - 5.0) * 0.3
            + hold_minutes
            + max(0.0, 200.0 - initial.temperature_c) * 0.2
        )
        # These threshold adjustments are illustrative, not validated criteria.
        flashing_pressure = procedure.boiling_initiation_pressure
        flashing_margin = (
            flashing_pressure - FLASHING_THRESHOLD_PRESSURE_MPA
            + (0.1 if flashing_pressure >= STABLE_TWO_PHASE_PRESSURE_MPA else 0.0)
            - (0.2 if flashing_pressure < FLASHING_THRESHOLD_PRESSURE_MPA else 0.0)
            + (initial.pressure_mpa - 0.1) * 0.02
            - (procedure.power_ramp_rate - 0.5) * 0.04
            + (procedure.inlet_subcooling - 5.0) * 0.006
            + hold_count * 0.02
            + hold_minutes * 0.001
        )
        density_wave_index = (
            45.0
            + (procedure.power_ramp_rate - 2.5) * 10.0
            - hold_count * 4.0 - hold_minutes * 0.05
        )
        pressure_oscillation_index = (
            30.0
            + procedure.pressure_ramp_rate * 12.0
            + abs(procedure.boiling_initiation_pressure - initial.pressure_mpa) * 2.0
            - hold_count * 2.0
            - hold_minutes * 0.03
        )
        thermal_stress = 50.0 + (procedure.pressure_ramp_rate - 0.8) * 20.0
        lost_generation_index = startup_time * 0.5
        operator_intervention_index = hold_count * 10.0
        thermal_stress_penalty = thermal_stress * 0.1
        return SimulationMetrics.from_mapping(
            {
                "startup_time_minutes": startup_time,
                "flashing_margin": flashing_margin,
                "density_wave_oscillation_index": max(0.0, density_wave_index),
                "pressure_oscillation_index": max(0.0, pressure_oscillation_index),
                "thermal_stress": max(0.0, thermal_stress),
                "lost_generation_index": lost_generation_index,
                "operator_intervention_index": operator_intervention_index,
                "thermal_stress_penalty": thermal_stress_penalty,
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
    boiling_pressure_bounds: tuple[float, float] = (0.1, 7.0)
    inlet_subcooling_bounds: tuple[float, float] = (5.0, 50.0)
    hold_duration_bounds: tuple[float, float] = (0.0, 60.0)
    hold_schedules: tuple[tuple[int, ...], ...] = DEFAULT_HOLD_SCHEDULES
    startup_types: tuple[StartupType, ...] = tuple(StartupType)

    def decode(self, vector: np.ndarray) -> StartupProcedure:
        """Convert a search vector into settings and a discrete hold schedule."""
        startup_type_index = int(
            np.clip(np.rint(vector[4]), 0, len(self.startup_types) - 1)
        )
        schedule_index = int(
            np.clip(np.rint(vector[5]), 0, len(self.hold_schedules) - 1)
        )
        duration = float(vector[6])
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
            startup_type=self.startup_types[startup_type_index],
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
                float(len(self.startup_types) - 1),
                float(len(self.hold_schedules) - 1),
                self.hold_duration_bounds[1],
            ]
        )
        return lower, upper


class _StartupProblem(ElementwiseProblem):
    """Pymoo problem delegating every evaluation to the configured backend."""

    def __init__(self, simulator: StartupSimulator, search_space: SearchSpace) -> None:
        lower, upper = search_space.bounds()
        super().__init__(n_var=7, n_obj=len(OBJECTIVES), xl=lower, xu=upper)
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
            procedure.startup_type.value,
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
        metrics = SimulationMetrics.from_mapping(self.records[key])
        out["F"] = metrics.objective_vector()


def _normalize_objectives(values: pd.DataFrame) -> pd.DataFrame:
    """Normalize objectives only for decision-support ranking."""
    normalized = pd.DataFrame(index=values.index)
    for name in OBJECTIVES:
        span = values[name].max() - values[name].min()
        if span == 0.0:
            normalized[name] = 0.0
        elif name in MAXIMIZE_OBJECTIVES:
            normalized[name] = (values[name].max() - values[name]) / span
        else:
            normalized[name] = (values[name] - values[name].min()) / span
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
    """Return compromise and single-objective best candidates."""
    if results.empty:
        raise ValueError("Cannot choose a procedure from an empty result set.")
    ranked = rank_pareto_candidates(results)
    return {
        "overall": ranked.iloc[0],
        "fastest": results.loc[results["startup_time_minutes"].idxmin()],
        "lowest_cost": results.loc[results["startup_cost"].idxmin()],
        "highest_flashing_margin": results.loc[
            results["flashing_margin"].idxmax()
        ],
        "lowest_dwo_index": results.loc[
            results["density_wave_oscillation_index"].idxmin()
        ],
        "lowest_pressure_oscillation_index": results.loc[
            results["pressure_oscillation_index"].idxmin()
        ],
    }


@dataclass(frozen=True)
class StartupProfile:
    name: str
    procedure: StartupProcedure


def comparison_startup_profiles(
    optimized: OptimizedStartupProcedure,
) -> tuple[StartupProfile, StartupProfile, StartupProfile]:
    """Return the named profile comparison set."""
    aggressive = StartupProcedure(
        power_ramp_rate=3.0,
        pressure_ramp_rate=1.0,
        boiling_initiation_pressure=0.4,
        inlet_subcooling=5.0,
        hold_schedule=(),
        startup_type=StartupType.HOT,
    )
    conservative = StartupProcedure(
        power_ramp_rate=0.5,
        pressure_ramp_rate=0.1,
        boiling_initiation_pressure=2.0,
        inlet_subcooling=35.0,
        hold_schedule=tuple(HoldPoint(level, 20.0) for level in (25, 50, 75)),
        startup_type=StartupType.COLD,
    )
    return (
        StartupProfile("Aggressive Startup", aggressive),
        StartupProfile("Conservative Startup", conservative),
        StartupProfile("Optimized Startup", optimized),
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
    metric_specs = (
        ("Flashing Margin", "flashing_margin", "MPa-equivalent estimate"),
        ("DWO Index", "density_wave_oscillation_index", "Index (backend-defined)"),
        (
            "Pressure Oscillation Index",
            "pressure_oscillation_index",
            "Index (backend-defined)",
        ),
    )
    figures: dict[str, plt.Figure] = {}

    figure, axes = plt.subplots(1, 3, figsize=(15, 4), squeeze=False)
    for axis, (label, column, ylabel) in zip(axes[0], metric_specs):
        axis.scatter(
            results["startup_time_minutes"],
            results[column],
            s=18,
            alpha=0.2,
            label="Evaluated",
        )
        axis.scatter(
            pareto["startup_time_minutes"],
            pareto[column],
            s=36,
            label="Pareto",
        )
        axis.set(title=label, xlabel="Startup time (min)", ylabel=ylabel)
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

    figure, axes = plt.subplots(1, 3, figsize=(15, 4), squeeze=False)
    for axis, (label, column, ylabel) in zip(axes[0], metric_specs):
        axis.scatter(
            results["startup_cost"],
            results[column],
            s=18,
            alpha=0.2,
            label="Evaluated",
        )
        axis.scatter(
            pareto["startup_cost"],
            pareto[column],
            s=36,
            label="Pareto",
        )
        axis.set(title=label, xlabel="Startup cost index", ylabel=ylabel)
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize="small")
    figures["cost_vs_risk"] = figure

    for name, plot in figures.items():
        plot.tight_layout()
        plot.savefig(output_path / f"{name}.png", dpi=160)

    time_metric_files = []
    cost_metric_files = []
    for label, column, _ in metric_specs:
        metric_slug = column.removesuffix("_index").replace("_", "-")
        time_filename = f"time_vs_{metric_slug}.html"
        px.scatter(
            results,
            x="startup_time_minutes",
            y=column,
            color="is_pareto",
            hover_data=["startup_cost", "thermal_stress", "power_ramp_rate"],
            title=f"Startup Duration vs {label}",
        ).write_html(output_path / time_filename)
        time_metric_files.append((label, time_filename))
    px.scatter(
        results,
        x="startup_time_minutes",
        y="startup_cost",
        color="is_pareto",
        title="Startup Time vs Cost",
    ).write_html(output_path / "time_vs_cost.html")
    for label, column, _ in metric_specs:
        metric_slug = column.removesuffix("_index").replace("_", "-")
        px.scatter(
            results,
            x="startup_cost",
            y=column,
            color="is_pareto",
            title=f"Startup Cost vs {label}",
        ).write_html(output_path / f"cost_vs_{metric_slug}.html")
        cost_metric_files.append((label, f"cost_vs_{metric_slug}.html"))
    for filename, title, metric_files in (
        ("time_vs_risk.html", "Startup Duration vs Stability Metrics", time_metric_files),
        ("cost_vs_risk.html", "Startup Cost vs Stability Metrics", cost_metric_files),
    ):
        panels = "".join(
            f'<section><h2>{label}</h2><iframe src="{metric_filename}" '
            'width="100%" height="450" loading="lazy"></iframe></section>'
            for label, metric_filename in metric_files
        )
        (output_path / filename).write_text(
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{title}</title></head><body><h1>{title}</h1>{panels}"
            "</body></html>\n",
            encoding="utf-8",
        )
    return figures


def generate_report(results: pd.DataFrame) -> str:
    """Summarize the Pareto compromise and its distinct stability metrics."""
    ranked = rank_pareto_candidates(results)
    best = ranked.iloc[0]
    hold_schedule = json.loads(best["hold_schedule"])
    lines = [
        "Recommended Pareto Compromise",
        f"Power ramp rate: {best['power_ramp_rate']:.3f} %FP/min",
        f"Pressure ramp rate: {best['pressure_ramp_rate']:.3f} MPa/min",
        f"Boiling initiation pressure: {best['boiling_initiation_pressure']:.3f} MPa",
        f"Inlet subcooling: {best['inlet_subcooling']:.2f} C",
        f"Startup type: {best['startup_type']}",
        f"Initial pressure: {best['initial_pressure_mpa']:.3f} MPa",
        f"Initial temperature: {best['initial_temperature_c']:.1f} C",
        f"Hold point schedule: {hold_schedule}",
        f"Startup time: {best['startup_time_minutes']:.2f} minutes",
        f"Flashing margin: {best['flashing_margin']:.3f} MPa-equivalent estimate",
        f"DWO index: {best['density_wave_oscillation_index']:.3f}",
        f"Pressure oscillation index: {best['pressure_oscillation_index']:.3f}",
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
            f"stability=(margin {candidate['flashing_margin']:.3f}, "
            f"DWO {candidate['density_wave_oscillation_index']:.3f}, "
            f"pressure oscillation {candidate['pressure_oscillation_index']:.3f})"
        )
    lines.extend(
        [
            "",
        "The selected candidate is a normalized compromise across the six backend "
        "outputs. Flashing margin, DWO index, and pressure oscillation index "
        "remain separate metrics.",
        "",
        "This recommendation depends on the configured backend or estimate "
        "model and its assumptions. It is not a plant operating procedure.",
        "When the built-in estimate model is active, these are illustrative "
        "literature-informed estimates, not predictive reactor simulations.",
        ]
    )
    return "\n".join(lines)


def _priority_winners(
    profile_metrics: Mapping[str, SimulationMetrics],
) -> dict[str, str]:
    """Return the profile that wins for each explicit priority mode."""
    speed_winner = min(
        profile_metrics,
        key=lambda name: profile_metrics[name].startup_time_minutes,
    )
    cost_winner = min(
        profile_metrics,
        key=lambda name: profile_metrics[name].startup_cost,
    )
    stability_winner = max(
        profile_metrics,
        key=lambda name: (
            profile_metrics[name].flashing_margin
            - 0.5 * profile_metrics[name].density_wave_oscillation_index
            - 0.5 * profile_metrics[name].pressure_oscillation_index
            - 0.25 * profile_metrics[name].thermal_stress
        ),
    )
    return {
        PriorityMode.STABILITY.value: stability_winner,
        PriorityMode.SPEED.value: speed_winner,
        PriorityMode.COST.value: cost_winner,
    }


def generate_priority_summary_chart(
    results: pd.DataFrame,
    simulator: StartupSimulator | None = None,
    output_path: str | Path = "results/improvements/priority_summary.png",
) -> plt.Figure:
    """Show the clear winner for each priority mode."""
    if results.empty:
        raise ValueError("Cannot summarize priorities from an empty result set.")
    simulator = simulator or LiteratureBasedEstimateSimulator()
    ranked = rank_pareto_candidates(results)
    selected_candidate = ranked.iloc[0]
    optimized = OptimizedStartupProcedure.from_candidate(selected_candidate)
    profiles = comparison_startup_profiles(optimized)
    profile_metrics = {
        profile.name: (
            SimulationMetrics.from_mapping(selected_candidate.to_dict())
            if profile.name == "Optimized Startup"
            else simulator.evaluate(profile.procedure)
        )
        for profile in profiles
    }
    winners = _priority_winners(profile_metrics)
    labels = ["Better for stability", "Better for speed/cost"]
    winner_names = [
        winners[PriorityMode.STABILITY.value],
        winners[PriorityMode.SPEED.value],
    ]
    colors = ["#2f6f4e", "#3467c8"]
    fig, axis = plt.subplots(figsize=(8, 4.5))
    bars = axis.bar(labels, [1.0, 1.0], color=colors, alpha=0.9, width=0.7)
    axis.set_ylim(0, 1.5)
    axis.set_yticks([])
    axis.set_title("BWRX-300 Startup Priority Summary")
    axis.set_ylabel("Winner by priority")
    for bar, winner in zip(bars, winner_names, strict=False):
        x = bar.get_x() + bar.get_width() / 2
        axis.text(
            x,
            0.45,
            winner,
            ha="center",
            va="center",
            fontsize=10,
            color="white",
            fontweight="bold",
        )
    for spine in (axis.spines["top"], axis.spines["right"]):
        spine.set_visible(False)
    axis.spines["left"].set_visible(False)
    axis.spines["bottom"].set_color("#444")
    fig.tight_layout()
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_file, dpi=180)
    return fig


def generate_improvement_report(
    results: pd.DataFrame,
    simulator: StartupSimulator | None = None,
    output_path: str | Path = "results/improvement_report.txt",
) -> str:
    """Produce a presentation-ready BWRX-300 startup comparison summary."""
    if results.empty:
        raise ValueError("Cannot compare procedures from an empty result set.")
    simulator = simulator or LiteratureBasedEstimateSimulator()
    ranked = rank_pareto_candidates(results)
    selected_candidate = ranked.iloc[0]
    optimized = OptimizedStartupProcedure.from_candidate(selected_candidate)
    profiles = comparison_startup_profiles(optimized)
    profile_metrics = {
        profile.name: (
            SimulationMetrics.from_mapping(selected_candidate.to_dict())
            if profile.name == "Optimized Startup"
            else simulator.evaluate(profile.procedure)
        )
        for profile in profiles
    }
    winners = _priority_winners(profile_metrics)
    baseline_name = "Conservative Startup"
    metric_names = (
        ("Flashing Margin", "flashing_margin", "higher"),
        ("DWO Index", "density_wave_oscillation_index", "lower"),
        ("Pressure Oscillation Index", "pressure_oscillation_index", "lower"),
        ("Thermal Stress", "thermal_stress", "lower"),
        ("Startup Duration", "startup_time_minutes", "lower"),
        ("Startup Cost", "startup_cost", "lower"),
    )
    lines = [
        _provenance_statement(simulator),
        "",
        "BWRX-300 startup comparison summary",
        "This comparison evaluates a baseline startup sequence against a Pareto-optimized",
        "startup strategy for a BWRX-300-style natural-circulation startup envelope.",
        "The results are literature-informed engineering estimates, not validated reactor",
        "transient predictions or operating limits.",
        "",
        "Priority-based interpretation",
        f"- Stability-priority winner: {winners[PriorityMode.STABILITY.value]}",
        f"- Speed-priority winner: {winners[PriorityMode.SPEED.value]}",
        f"- Cost-priority winner: {winners[PriorityMode.COST.value]}",
        "- Overall compromise candidate: Optimized Startup",
        "",
        "Startup profiles",
    ]
    for profile in profiles:
        conditions = profile.procedure.initial_conditions
        lines.extend(
            [
                profile.name,
                f"  Type: {profile.procedure.startup_type.value}",
                f"  Initial pressure: {conditions.pressure_mpa:.3f} MPa",
                f"  Initial temperature: {conditions.temperature_c:.1f} C",
                f"  Power ramp: {profile.procedure.power_ramp_rate:.3f} %FP/min",
                f"  Pressure ramp: {profile.procedure.pressure_ramp_rate:.3f} MPa/min",
                f"  Hold points: {len(profile.procedure.hold_schedule)}",
            ]
        )
    lines.extend(
        [
            "",
            "Direct metric comparison",
            f"{'Metric':<30} {'Aggressive':>14} {'Conservative':>14} "
            f"{'Optimized':>14} {'Improvement %':>16}",
            "-" * 94,
        ]
    )
    baseline = profile_metrics[baseline_name]
    optimized_metrics = profile_metrics["Optimized Startup"]
    improvement_rows = []
    for label, name, direction in metric_names:
        values = {
            profile_name: float(getattr(metrics, name))
            for profile_name, metrics in profile_metrics.items()
        }
        baseline_value = float(getattr(baseline, name))
        optimized_value = float(getattr(optimized_metrics, name))
        if baseline_value == 0.0:
            improvement = "N/A"
        elif direction == "higher":
            improvement = f"{(optimized_value - baseline_value) / abs(baseline_value) * 100.0:+.2f}%"
        else:
            improvement = f"{(baseline_value - optimized_value) / abs(baseline_value) * 100.0:+.2f}%"
        improvement_rows.append((label, baseline_value, optimized_value, improvement))
        lines.append(
            f"{label:<30} {values['Aggressive Startup']:>14.3f} "
            f"{baseline_value:>14.3f} {optimized_value:>14.3f} "
            f"{improvement:>16}"
        )
    lines.extend(
        [
            "",
            "Baseline versus optimized startup",
            "The conservative startup profile is used as the baseline reference for the",
            "comparison. Positive percent change indicates movement in the preferred",
            "direction for that metric.",
            f"{'Metric':<30} {'Baseline':>14} {'Optimized':>14} "
            f"{'Improvement %':>16}",
            "-" * 78,
        ]
    )
    lines.extend(
        f"{label:<30} {baseline_value:>14.3f} "
        f"{optimized_value:>14.3f} {improvement:>16}"
        for label, baseline_value, optimized_value, improvement in improvement_rows
    )
    lines.extend(
        [
            "",
            "Engineering interpretation",
            "The optimized profile is selected as a balanced compromise across startup",
            "duration, startup cost, and stability margins. It is not the lowest-risk profile",
            "for every metric, and it is not the fastest profile in every case; instead, it",
            "represents the best overall tradeoff within the modelled startup envelope.",
            "For a stability-focused startup, the conservative profile remains the best fit.",
            "For a time- and cost-driven startup, the aggressive profile is preferred.",
            "For a balanced BWRX-300 decision case, the optimized profile is the preferred",
            "overall compromise in this framework.",
            "Startup cost index = lost_generation_index + operator_intervention_index +",
            "thermal_stress_penalty.",
            "The 0.4 MPa flashing threshold and 0.7 MPa stable two-phase threshold remain",
            "demonstration-only thresholds for the literature-informed estimate model.",
            "This comparison does not represent validated reactor startup predictions.",
        ]
    )
    report = "\n".join(lines)
    report_file = Path(output_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report + "\n", encoding="utf-8")
    return report


def generate_improvement_charts(
    results: pd.DataFrame,
    simulator: StartupSimulator | None = None,
    output_directory: str | Path = "results/improvements",
) -> dict[str, plt.Figure]:
    """Create presentation-ready baseline-vs-optimized bar charts."""
    if results.empty:
        raise ValueError("Cannot compare procedures from an empty result set.")
    simulator = simulator or LiteratureBasedEstimateSimulator()
    ranked = rank_pareto_candidates(results)
    selected_candidate = ranked.iloc[0]
    optimized = OptimizedStartupProcedure.from_candidate(selected_candidate)
    profiles = comparison_startup_profiles(optimized)
    profile_metrics = {
        profile.name: (
            SimulationMetrics.from_mapping(selected_candidate.to_dict())
            if profile.name == "Optimized Startup"
            else simulator.evaluate(profile.procedure)
        )
        for profile in profiles
    }
    baseline_name = "Conservative Startup"
    metric_specs = (
        ("Flashing Margin", "flashing_margin", "higher"),
        ("DWO Index", "density_wave_oscillation_index", "lower"),
        ("Pressure Oscillation Index", "pressure_oscillation_index", "lower"),
        ("Thermal Stress", "thermal_stress", "lower"),
    )
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)
    figures: dict[str, plt.Figure] = {}
    for label, name, direction in metric_specs:
        baseline_value = float(getattr(profile_metrics[baseline_name], name))
        optimized_value = float(getattr(profile_metrics["Optimized Startup"], name))
        fig, axis = plt.subplots(figsize=(6, 4))
        bars = axis.bar(
            ["Baseline", "Optimized"],
            [baseline_value, optimized_value],
            color=["#6b7280", "#2f6f4e"],
            width=0.7,
        )
        axis.set_title(f"Baseline vs Optimized {label}")
        axis.set_ylabel(label)
        axis.grid(True, axis="y", alpha=0.25)
        if direction == "higher":
            axis.set_ylim(bottom=0)
        else:
            axis.set_ylim(bottom=0)
        for bar, value in zip(bars, [baseline_value, optimized_value], strict=False):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(abs(value) * 0.03, 0.2),
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
        fig.tight_layout()
        filename = f"baseline_vs_optimized_{label.lower().replace(' ', '_').replace('-', '_')}.png"
        fig.savefig(output_path / filename, dpi=180)
        figures[label] = fig
    return figures


def _provenance_statement(simulator: StartupSimulator) -> str:
    if isinstance(simulator, LiteratureBasedEstimateSimulator):
        return (
            "LITERATURE-BASED ESTIMATES: qualitative trend demonstration only; "
            "not validated correlations or reactor performance predictions."
        )
    return (
        "EXTERNAL SIMULATOR OUTPUTS: validation status depends on the configured "
        "backend; this optimizer does not certify model validity."
    )


def _stability_sensitivity_score(
    baseline: SimulationMetrics,
    alternative: SimulationMetrics,
) -> float:
    """Return mean fractional change across margin and two stability indices."""
    effects = []
    for name in (
        "flashing_margin",
        "density_wave_oscillation_index",
        "pressure_oscillation_index",
    ):
        reference = float(getattr(baseline, name))
        changed = float(getattr(alternative, name))
        scale = max(abs(reference), 0.1)
        effects.append(abs(changed - reference) / scale)
    return sum(effects) / len(effects)


def perform_sensitivity_analysis(
    simulator: StartupSimulator,
    search_space: SearchSpace = SearchSpace(),
) -> pd.DataFrame:
    """Rank input-variable effects using one-at-a-time sensitivity estimates."""
    reference = BaselineStartupProcedure()
    baseline_metrics = simulator.evaluate(reference)
    comparisons = {
        "power_ramp_rate": [
            replace(reference, power_ramp_rate=value)
            for value in search_space.power_ramp_bounds
        ],
        "pressure_ramp_rate": [
            replace(reference, pressure_ramp_rate=value)
            for value in search_space.pressure_ramp_bounds
        ],
        "boiling_initiation_pressure": [
            replace(reference, boiling_initiation_pressure=value)
            for value in search_space.boiling_pressure_bounds
        ],
        "inlet_subcooling": [
            replace(reference, inlet_subcooling=value)
            for value in search_space.inlet_subcooling_bounds
        ],
        "startup_type": [
            replace(reference, startup_type=startup_type)
            for startup_type in search_space.startup_types
        ],
        "hold_schedule": [
            replace(
                reference,
                hold_schedule=tuple(HoldPoint(level, 20.0) for level in schedule),
            )
            for schedule in search_space.hold_schedules
        ],
        "hold_duration_minutes": [
            replace(
                reference,
                hold_schedule=tuple(
                    HoldPoint(level, duration) for level in (25, 50, 75)
                ),
            )
            for duration in search_space.hold_duration_bounds
        ],
    }
    rows = []
    for variable, procedures in comparisons.items():
        scores = [
            _stability_sensitivity_score(
                baseline_metrics,
                simulator.evaluate(procedure),
            )
            for procedure in procedures
        ]
        rows.append(
            {
                "variable": variable,
                "importance_score": max(scores, default=0.0),
            }
        )
    return pd.DataFrame(rows).sort_values(
        "importance_score", ascending=False
    ).reset_index(drop=True)


def generate_sensitivity_report(
    simulator: StartupSimulator,
    output_path: str | Path = "results/sensitivity_analysis.txt",
) -> tuple[pd.DataFrame, str]:
    """Write and return a ranked one-at-a-time sensitivity summary."""
    importance = perform_sensitivity_analysis(simulator)
    lines = [
        _provenance_statement(simulator),
        "",
        "Ranked Variable Importance (one-at-a-time stability sensitivity)",
        "Scores are relative to the baseline and depend on the selected "
        "estimate/backend and parameter bounds.",
    ]
    lines.extend(
        f"{rank}. {row.variable}: {row.importance_score:.4f}"
        for rank, row in enumerate(importance.itertuples(index=False), start=1)
    )
    report = "\n".join(lines)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report + "\n", encoding="utf-8")
    return importance, report


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
    """Run NSGA-II with the selected simulator and export comparison reports."""
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
    generate_improvement_charts(results, simulator, "results/improvements")
    _, sensitivity_report = generate_sensitivity_report(simulator)
    priority_summary = generate_priority_summary_chart(results, simulator)
    print(f"Recorded {len(results):,} unique simulator evaluations.")
    print(f"Pareto candidates: {int(results['is_pareto'].sum()):,}")
    print(
        "Saved startup_optimization_results.csv, Pareto plots, improvement charts, "
        "priority summary, and sensitivity reports under results/."
    )
    print("\nPriority summary chart saved to results/improvements/priority_summary.png")
    print("\n" + report)
    print("\n" + improvement_report)
    print("\n" + sensitivity_report)


if __name__ == "__main__":
    main()
