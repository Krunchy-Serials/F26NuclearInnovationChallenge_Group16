"""MOOSE THM transient execution and optimizer adapter factory."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .input_generator import generate_input_deck
from .metrics import extract_simulation_metrics
from .parser import TransientColumnMap, TransientOutput, parse_transient_csv


@dataclass(frozen=True)
class MooseRunConfig:
    """Executable, deck template, outputs, and column mapping for one MOOSE app."""

    executable: str
    input_template: Path
    run_directory: Path
    output_csv_name: str = "startup_out.csv"
    timeout_seconds: float = 3_600.0
    extra_arguments: tuple[str, ...] = ()
    mpi_launcher: tuple[str, ...] = ()
    columns: TransientColumnMap = TransientColumnMap()

    @classmethod
    def from_environment(cls) -> MooseRunConfig:
        """Load run settings from MOOSE_* environment variables."""
        executable = os.environ.get("MOOSE_EXECUTABLE")
        template_value = os.environ.get("MOOSE_INPUT_TEMPLATE")
        completion_value = os.environ.get("MOOSE_COMPLETION_POWER")
        if not executable or not template_value or not completion_value:
            raise RuntimeError(
                "Set MOOSE_EXECUTABLE, MOOSE_INPUT_TEMPLATE, and "
                "MOOSE_COMPLETION_POWER before creating the simulator."
            )

        time_unit = os.environ.get("MOOSE_TIME_UNIT", "s")
        columns = TransientColumnMap(
            time=os.environ.get("MOOSE_TIME_COLUMN", "time"),
            power=os.environ.get("MOOSE_POWER_COLUMN", "power"),
            pressure=os.environ.get("MOOSE_PRESSURE_COLUMN", "pressure"),
            void_fraction=os.environ.get("MOOSE_VOID_FRACTION_COLUMN", "void_fraction"),
            mass_flow=os.environ.get("MOOSE_MASS_FLOW_COLUMN", "mass_flow"),
            fluid_temperature=os.environ.get(
                "MOOSE_FLUID_TEMPERATURE_COLUMN", "fluid_temperature"
            ),
            cladding_temperature=os.environ.get(
                "MOOSE_CLADDING_TEMPERATURE_COLUMN", "cladding_temperature"
            ),
            time_unit=time_unit,
            completion_power=float(completion_value),
        )
        timeout_seconds = float(os.environ.get("MOOSE_TIMEOUT_SECONDS", "3600"))
        if timeout_seconds <= 0.0:
            raise ValueError("MOOSE_TIMEOUT_SECONDS must be positive.")

        template = Path(template_value).expanduser().resolve()
        if not template.is_file():
            raise FileNotFoundError(f"MOOSE input template not found: {template}")
        resolved_executable = shutil.which(executable)
        if resolved_executable is None:
            candidate = Path(executable).expanduser()
            if not candidate.is_file():
                raise FileNotFoundError(f"MOOSE executable not found: {executable}")
            resolved_executable = str(candidate.resolve())

        return cls(
            executable=resolved_executable,
            input_template=template,
            run_directory=Path(
                os.environ.get("MOOSE_RUN_DIRECTORY", "moose_runs")
            ).expanduser().resolve(),
            output_csv_name=os.environ.get("MOOSE_OUTPUT_CSV", "startup_out.csv"),
            timeout_seconds=timeout_seconds,
            extra_arguments=tuple(shlex.split(os.environ.get("MOOSE_EXTRA_ARGUMENTS", ""))),
            mpi_launcher=tuple(shlex.split(os.environ.get("MOOSE_MPI_LAUNCHER", ""))),
            columns=columns,
        )


@dataclass(frozen=True)
class MooseTransientRun:
    """Artifacts from a completed MOOSE transient and its parsed output table."""

    run_directory: Path
    input_deck: Path
    output_csv: Path
    transient: TransientOutput
    stdout_path: Path
    stderr_path: Path


def run_moose_transient(
    procedure: Any,
    config: MooseRunConfig,
) -> MooseTransientRun:
    """Render and execute one MOOSE transient, then parse its configured CSV.

    The generated deck remains model-specific: the template must already contain
    the reactor geometry, THM components, initial/boundary conditions, controls,
    transient executioner, and CSV output setup appropriate to the study.
    """
    if Path(config.output_csv_name).name != config.output_csv_name:
        raise ValueError("MOOSE_OUTPUT_CSV must be a filename within each run folder.")
    if not config.output_csv_name.lower().endswith(".csv"):
        raise ValueError("MOOSE_OUTPUT_CSV must use the .csv extension.")

    run_id = uuid.uuid4().hex
    run_directory = config.run_directory / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    deck = generate_input_deck(
        procedure,
        config.input_template,
        run_directory / "startup.i",
        output_csv_name=config.output_csv_name,
    )
    stdout_path = run_directory / "stdout.log"
    stderr_path = run_directory / "stderr.log"
    command = [
        *config.mpi_launcher,
        config.executable,
        *config.extra_arguments,
        "-i",
        deck.name,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=run_directory,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout_path.write_text(str(error.stdout or ""), encoding="utf-8")
        stderr_path.write_text(str(error.stderr or ""), encoding="utf-8")
        raise TimeoutError(
            f"MOOSE transient exceeded {config.timeout_seconds:g} seconds; "
            f"logs are in {run_directory}."
        ) from error

    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"MOOSE exited with status {completed.returncode}; inspect "
            f"{stdout_path} and {stderr_path}."
        )

    output_csv = run_directory / config.output_csv_name
    transient = parse_transient_csv(output_csv, config.columns)
    return MooseTransientRun(
        run_directory=run_directory,
        input_deck=deck,
        output_csv=output_csv,
        transient=transient,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def _procedure_from_payload(payload: dict[str, Any]) -> Any:
    """Adapt the stable payload contract to startup_optimization dataclasses."""
    from startup_optimization import HoldPoint, StartupProcedure

    return StartupProcedure(
        power_ramp_rate=float(payload["power_ramp_rate"]),
        pressure_ramp_rate=float(payload["pressure_ramp_rate"]),
        boiling_initiation_pressure=float(payload["boiling_initiation_pressure"]),
        inlet_subcooling=float(payload["inlet_subcooling"]),
        hold_schedule=tuple(
            HoldPoint(
                power_percent=int(point["power_percent"]),
                duration_minutes=float(point["duration_minutes"]),
            )
            for point in payload["hold_schedule"]
        ),
    )


def _metric_runner(config: MooseRunConfig):
    """Create the callable expected by startup_optimization.MOOSETHMAdapter."""

    def evaluate(payload: dict[str, Any]) -> dict[str, float]:
        procedure = _procedure_from_payload(payload)
        completed_run = run_moose_transient(procedure, config)
        return extract_simulation_metrics(completed_run.transient)

    return evaluate


def create_simulator():
    """Return a configured MOOSETHMAdapter for STARTUP_SIMULATOR loading."""
    from startup_optimization import MOOSETHMAdapter

    config = MooseRunConfig.from_environment()
    return MOOSETHMAdapter(_metric_runner(config))
