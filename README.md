# F26 Nuclear Innovation Challenge – Group 16

This repository explores multi-objective optimization of nuclear startup procedures using a Pareto-based search strategy. `startup_optimization.py` compares and optimizes startup profiles with three
separate stability metrics: flashing margin, density-wave oscillation index,
and pressure-oscillation index. It also tracks thermal stress, startup
duration, and a startup-cost index.

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

- `startup_optimization.py` – BWRX-300 startup optimization and reporting framework
- `backend/` – solver-specific backend adapters and MOOSE THM integration
- `requirements.txt` – Python dependencies
- `LICENSE` – project license

## What the optimizer does

The optimizer uses the following structure:

1. Defines a search space for startup variables
2. Encodes each candidate as a `StartupProcedure`
3. Sends a JSON-like payload to the configured simulator backend
4. Validates outputs as `SimulationMetrics`
5. Optimizes six objective values:
   - startup time
   - flashing margin (higher is preferred)
   - density-wave oscillation index
   - pressure-oscillation index
   - thermal stress
   - startup cost
6. Runs NSGA-II across many candidate designs
7. Identifies Pareto-front solutions and ranks them with a normalized score
8. Writes results to `startup_optimization_results.csv` and under `results/`

The search includes COLD, WARM, and HOT categories with different illustrative
initial pressure and temperature conditions. The default condition values are
demonstration placeholders, not BWRX-300 data.

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
- `results/time_vs_risk.png` (separate axes per stability metric)
- `results/time_vs_cost.png` and `.html`
- `results/cost_vs_risk.png` (separate axes per stability metric)
- metric-specific interactive HTML plots under `results/`
- `results/startup_optimization_report.txt`
- `results/improvement_report.txt`
- `results/improvements/` with presentation-ready bar charts for baseline vs optimized metrics
- `results/sensitivity_analysis.txt`

## Parameter Selection and Literature Validation

This project uses a literature-informed parameter set to bound the startup optimization framework. These values are intentionally separated into:

- validated literature parameters: pressure thresholds and subcooling levels
- engineering assumptions: startup ramps, hold points, and scoring functions

### 1) Pressure range: 0.1 MPa – 0.7 MPa

The search space uses a low-pressure start at approximately 0.1 MPa and a stable two-phase circulation regime at about 0.7 MPa. Stable two-phase circulation was achieved above approximately 0.7 MPa in the startup instability experiments reported by Subki et al. This is a literature-supported lower bound for stable circulation during startup, and it is used as a validation anchor for the pressure range in this repository. See [Subki et al. startup instability experiments][subki-startup].

### 2) Flashing instability threshold: 0.4 MPa

The flashing-instability threshold used in the estimator is 0.4 MPa. This is based on the Purdue BWR-type SMR stability maps, where the flashing-instability boundary approaches the zero-quality boundary near this pressure. This makes 0.4 MPa a useful pressure boundary for identifying the onset of flashing-related instability in a literature-informed startup approximation. See [Purdue BWR-type SMR stability maps][purdue-smr].

### 3) Inlet subcooling: 5 K, 10 K, 15 K

The inlet-subcooling levels used here follow the natural-circulation startup instability experiments. The literature-supported subcooling conditions used for the framework are 5 K, 10 K, and 15 K. These values are used as validated operating points for evaluating stability sensitivity, while the startup ramps and hold schedules remain engineering approximations. See [Natural-circulation startup instability experiments][natural-circulation-startup].

### 4) Startup classifications

The project uses the following startup definitions:

| Startup classification | Initial pressure | Inlet subcooling | Status |
|---|---:|---:|---|
| Cold Startup | 0.1 MPa | 15 K | Literature-based startup condition |
| Warm Startup | 0.7 MPa | 10 K | Literature-based startup condition |
| Hot Startup | 2.0 MPa | 5 K | Engineering assumption for demonstration only |

The Hot Startup values are explicitly engineering assumptions for the optimization framework and not a validated reactor-specific operating condition. The pressure and subcooling values for Cold and Warm Startup are anchored to the cited literature; the Hot Startup values are a demonstration extension used to compare startup types in the optimization workflow.

## Profile comparison and limitations

The run compares Aggressive, Conservative, and Pareto-optimized profiles, ranks variable importance using a one-at-a-time sensitivity analysis, and applies demonstration adjustments at the 0.4 MPa flashing and 0.7 MPa stable two-phase thresholds. These thresholds are from the literature sources listed above and are used here as validation anchors for the estimate model.

The built-in factors translate qualitative literature-informed trends into transparent illustrative estimates. They are not numerical correlations taken from a validated BWRX-300 reactor model, and their outputs must not be presented as predictive reactor simulations. Startup cost is the sum of illustrative lost-generation, operator-intervention, and thermal-stress-penalty indices; it is not a currency or plant-cost estimate. A validated MOOSE THM or OpenFOAM/GeN-Foam backend can replace these estimates by setting `STARTUP_SIMULATOR`; see [backend setup](backend/README.md).

The comparison is saved to `results/improvement_report.txt`, and the ranked variable importance is saved to `results/sensitivity_analysis.txt`.

### Limitations

Validated literature parameters:
- pressure thresholds from startup instability experiments and stability maps
- subcooling levels from natural-circulation startup instability experiments

Engineering assumptions:
- power and pressure ramp rates
- hold points and hold durations
- scoring and normalization functions used to rank startup candidates

This project is a literature-informed startup optimization framework and not a validated reactor simulation. Any real plant application must use approved models, validation data, uncertainty treatment, and operational review before implementation.

## Outputs and interpretation

`startup_optimization.py` writes:

- a full results table with per-candidate decision metrics
- a Pareto flag for each candidate
- a compromise score for ranking candidates
- plots showing trade-offs between startup duration, cost, and stability metrics
- `results/improvement_report.txt` comparing the three startup profiles
- `results/sensitivity_analysis.txt` with a ranked one-at-a-time importance list

Interpretation should always consider backend validation, data quality, and assumptions behind every metric. Percent improvements are relative to the baseline values; negative startup-time or cost percentages are labeled as worsened performance. The optimizer is decision-support infrastructure, not a validated startup procedure for plant operations.

## References

- [Subki et al. startup instability experiments][subki-startup]
- [Purdue BWR-type SMR stability maps][purdue-smr]
- [Natural-circulation startup instability experiments][natural-circulation-startup]

[subki-startup]: Subki, A. et al., startup instability experiments for natural-circulation systems; pressure range and stable two-phase circulation behavior used to bound the pressure search space.
[purdue-smr]: Purdue University BWR-type small modular reactor stability maps; the flashing-instability boundary near the zero-quality limit used to select the 0.4 MPa threshold.
[natural-circulation-startup]: Natural-circulation startup instability experiments; inlet-subcooling levels of 5 K, 10 K, and 15 K used to represent validated literature subcooling conditions.

## Safety note

The project explicitly does not provide a ready-to-use startup procedure for a reactor. Any real plant application must use approved models, validation data, uncertainty treatment, and operational review before implementation.
