# F26 Nuclear Innovation Challenge – Group 16

This repository explores multi-objective optimization of nuclear startup procedures using a Pareto-based search strategy. `startup_optimization.py` supports an explicitly illustrative, literature-informed trend-estimate mode by default, as well as configured external simulation backends.

## Overview

`startup_optimization.py` is designed to:

- search a startup design space using NSGA-II
- encode startup parameters such as power ramp rate, pressure ramp rate, boiling initiation pressure, inlet subcooling, and hold points
- estimate or simulate each candidate through a common backend interface
- validate the simulator outputs against a required metric contract
- rank pareto-efficient candidates using a decision-support score
- save CSV, HTML, PNG, and text outputs for review

This is research and decision-support tooling, not a plant operating procedure. The built-in estimate model demonstrates the workflow only; its factors are not validated literature correlations or predictive reactor simulation results.

## Repository layout

- `startup_optimization.py` – optimizer and reporting framework
- `backend/` – solver-specific backend adapters and MOOSE THM integration
- `burnup_analysis.py` and `burnup_optimization.py` – related analysis workflows
- `requirements.txt` – Python dependencies
- `LICENSE` – project license

## What the optimizer does

The optimizer uses the following structure:

1. Defines a search space for startup variables
2. Encodes each candidate as a `StartupProcedure`
3. Sends a JSON-like payload to the configured simulator backend
4. Validates outputs as `SimulationMetrics`
5. Minimizes six objective values:
   - startup time
   - flashing instability risk
   - density-wave oscillation risk
   - geysering risk
   - thermal stress
   - startup cost
6. Runs NSGA-II across many candidate designs
7. Identifies Pareto-front solutions and ranks them with a normalized score
8. Writes results to `startup_optimization_results.csv` and under `results/`

The top candidate is a compromise across all objectives, not a single combined instability equation. Risk metrics remain separate and must be interpreted with the backend model's validation and uncertainty treatment.

## Required backend

To use an external simulator instead of the built-in illustrative estimate model, expose a factory through the environment variable:

```bash
export STARTUP_SIMULATOR=package.module:create_simulator
```

The included MOOSE THM backend is wired as:

```bash
export STARTUP_SIMULATOR=backend.moose_thm:create_simulator
```

This backend requires additional MOOSE environment variables such as:

```bash
export MOOSE_EXECUTABLE=/path/to/your/thm-app-opt
export MOOSE_INPUT_TEMPLATE=/path/to/your/model/startup_template.i
export MOOSE_COMPLETION_POWER=1.0
```

See the backend documentation in `backend/README.md` for the complete configuration details.

## Quick start

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the optimizer with its built-in illustrative estimate model:

```bash
python startup_optimization.py
```

Or export a configured simulator factory before running:

```bash
export STARTUP_SIMULATOR=your_module:create_simulator
python startup_optimization.py
```

This produces:

- `startup_optimization_results.csv`
- `results/time_vs_risk.png` and `.html`
- `results/time_vs_cost.png` and `.html`
- `results/cost_vs_risk.png` and `.html`
- `results/startup_optimization_report.txt`
- `results/improvements/improvement_summary.txt`
- four baseline-versus-optimized comparison charts under `results/improvements/`

## Baseline comparison and estimate limitations

The run compares a baseline procedure (2.5 %FP/min power ramp, 0.8 MPa/min
pressure ramp, 2.0 MPa boiling initiation pressure, 10 C inlet subcooling, and
no hold points) against the top-ranked Pareto candidate. The report includes
the six metric estimates, percent changes, and separate bar charts for flashing
risk, density-wave oscillation (DWO) risk, geysering risk, and thermal stress.

The built-in factors translate the supplied qualitative literature-informed
trends into transparent illustrative estimates. They are not numerical
correlations taken from cited BWRX-300 studies, and their outputs must not be
presented as predictive reactor simulations. A validated MOOSE THM or
OpenFOAM/GeN-Foam backend can replace these estimates by setting
`STARTUP_SIMULATOR`; see [backend setup](backend/README.md).

The estimate model encodes these directions: faster power ramps increase
flashing and DWO risk; lower boiling-initiation pressure increases flashing
risk; additional holds reduce instability indices; higher pressure reduces
geysering risk; faster pressure ramps increase the thermal-stress index; and
greater inlet subcooling lowers flashing risk while increasing estimated
startup time. The numerical sensitivity factors are transparent demonstration
choices, not values derived from a cited BWRX-300 data set. Startup cost is a
relative time-based index, not a currency or plant-cost estimate.

## Outputs and interpretation

`startup_optimization.py` writes:

- a full results table with per-candidate decision metrics
- a Pareto flag for each candidate
- a compromise score for ranking candidates
- plots showing trade-offs between startup time, cost, and risk metrics
- a text summary report

Interpretation should always consider backend validation, data quality, and assumptions behind every metric. Percent improvements are relative to the baseline values; negative startup-time or cost percentages are labeled as worsened performance. The optimizer is decision-support infrastructure, not a validated startup procedure for plant operations.

## Safety note

The project explicitly does not provide a ready-to-use startup procedure for a reactor. Any real plant application must use approved models, validation data, uncertainty treatment, and operational review before implementation.
