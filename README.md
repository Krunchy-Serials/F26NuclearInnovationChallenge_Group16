# F26 Nuclear Innovation Challenge – Group 16

This repository is a research framework for evaluating startup strategies for
BWRX-300 small modular reactors (SMRs). Its current built-in equations are
unvalidated heuristic scores—not a predictive BWR or BWRX-300 model.
Peer-reviewed BWR research informs the phenomena to study, but does not validate
the project's coefficients or establish BWRX-300 operating conditions.

## Overview

`startup_optimization.py` is designed to:

- search a startup design space using NSGA-II
- encode startup parameters such as power ramp rate, pressure ramp rate, boiling initiation pressure, inlet subcooling, and hold points
- evaluate each candidate through an explicitly configured simulator backend
- validate the simulator outputs against a required metric contract
- rank pareto-efficient candidates using a decision-support score
- save CSV, HTML, PNG, and text outputs for review

This is research tooling, not a plant operating procedure. Without a configured
external simulator, the optimizer prints public-evidence status and produces no
scores. An illustrative heuristic mode is available only by explicit opt-in
(`python startup_optimization.py --illustrative` or
`STARTUP_ESTIMATE_MODE=illustrative`) and writes to a separate output directory.

`type2_stability_analysis.py` reports the public Type 2 stability evidence
status by default. Its optional `--illustrative` mode ranks conditions using a
project-assumption index. Those coefficients and the BWRX-300-labeled example
are not plant data or a validated reactor simulation.

See the [public BWR benchmark review](public_bwr_benchmark_review.md) for the
available literature, data limitations, and validation requirements.
Run `python plot_public_bwr_evidence.py` to generate six figures under
`results/literature_evidence/`. In addition to the published Peach Bottom 2
turbine-trip comparison and evidence-status figures, the script plots
literature-reported Type I/II density-wave classifications and generic
experimental startup-loop observations. Approximate digitization and
facility-specific scope are called out in the figures; none is BWRX-300
validation or a reactor simulation.

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
8. Writes results to CSV, plots, and text reports

The illustrative search includes COLD, WARM, and HOT categories with different
placeholder initial pressures and temperatures. These are not BWRX-300 data.

## Simulator backend

The repository does not contain a BWRX-300 model, validated transient
correlations, or measured BWRX-300 startup data. A public BWR research model
could support a research prototype, but any transfer to BWRX-300 would remain an
estimate until validated against BWRX-300-specific data and an applicable
system/geometry model.

For normal optimizer runs, configure an external simulator factory through the
environment variable:

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

Run with a configured simulator factory:

```bash
export STARTUP_SIMULATOR=your_module:create_simulator
python startup_optimization.py
```

The included MOOSE integration is an adapter, not a supplied BWRX-300 model.
Its metric extractors intentionally raise `NotImplementedError` until valid
methods and required transient/model data are provided. See
[backend documentation](backend/README.md).

To generate workflow-only outputs using the unvalidated heuristic equations,
explicitly opt in:

```bash
export STARTUP_ESTIMATE_MODE=illustrative
python startup_optimization.py
```

These heuristic outputs are isolated under `results/illustrative_heuristic/`
and must not be interpreted as research-backed performance comparisons. With an
external backend, outputs are written under `results/`; the backend owner is
responsible for validation evidence and metric provenance.

The report and charts include:

- Pareto search results as CSV
- duration/cost/stability tradeoff plots
- profile comparison and sensitivity reports

## Evidence and Assumption Register

The built-in `IllustrativeHeuristicSimulator` does **not** calculate reactor
physics. It is a heuristic demonstration model. Peer-reviewed BWR and
natural-circulation studies support the relevance of flashing, geysering,
density-wave oscillations, pressure, heat flux, and subcooling to startup
stability. They do not validate this repository's numerical equations,
coefficients, optimized settings, or BWRX-300 performance.

### Assumptions currently used

| Model element | Current assumption | Evidence status |
|---|---|---|
| Startup duration | `150 / rN + 0.3(ΔTsub − 5) + hold_minutes + 0.2 max(0, 200 − T0)` | All constants are project-invented. Duration should instead be measured from the transient power history and a defined completion criterion. |
| Flashing-margin score | `Pb − 0.4 + 0.1 if Pb≥0.7 − 0.2 if Pb<0.4 + 0.02(P0−0.1) − 0.04(rN−0.5) + 0.006(ΔTsub−5) + 0.02n + 0.001H` | It is not a physical margin and has no valid unit; “MPa-equivalent” is not appropriate. The cutoffs/bonus are not universal thresholds. Subki et al. observed multiple instabilities through 0.7 MPa, with stable two-phase circulation reported only above 0.7 MPa after oscillations were suppressed in that facility. Not a BWRX-300 limit. |
| DWO index | `max(0, 45 + 10(rN−2.5) − 4n − 0.05H)` | Base and coefficients are arbitrary. Research supports DWO and offers physical/model-based methods; this implementation does not implement or validate one. |
| Pressure-oscillation index | `max(0, 30 + 12rP + 2|Pb−P0| − 2n − 0.03H)` | Base and coefficients are arbitrary; there is no defined signal-processing, frequency, or experimental calibration basis. |
| Thermal-stress index | `max(0, 50 + 20(rP−0.8))` | Not a stress calculation. Actual stress/fatigue requires component geometry, material properties, transient thermal boundary conditions, and structural analysis. |
| Startup-cost index | `0.5 × duration + 10 × hold_count + 0.1 × thermal_stress_score` | Factors and units are arbitrary. `10 × hold_count` is not measured operator workload; total is neither currency nor a validated cost index. |
| Startup conditions | COLD 0.1 MPa/20°C; WARM 0.7 MPa/120°C; HOT 2 MPa/200°C | Demonstration values, not BWRX-300 operating conditions. Subki et al.'s 5/10/15 K conditions apply to their experimental loop, not this reactor's validated startup setpoints. |
| Baseline and comparison profiles | Baseline dataclass: 2.5 %FP/min power ramp, 0.8 MPa/min pressure ramp, 2 MPa boiling pressure, 10 K subcooling, no holds. Comparison report baseline: separate Conservative case (0.5 %FP/min, 0.1 MPa/min, 2 MPa, 35 K, three 20-min holds). | Hard-coded demo profiles, not approved procedures. The comparison report's “baseline” is not the `BaselineStartupProcedure` dataclass. |
| Search bounds and discretization | Power ramp 0.5–3; pressure ramp 0.1–1 MPa/min; boiling pressure 0.1–7 MPa; subcooling 5–50 K; hold duration 0–60 min; holds at 25/50/75%; duration is identical at every hold. | Chosen for the demonstration, not BWRX-300 operating/safety limits. Several values exceed Subki et al.'s experimental range. |
| Units and score handling | Pressure in MPa, ramp units as shown, subcooling as a temperature difference; negative DWO/stress scores are floored at zero. | Inputs are not tied to an enforced common validated unit contract; combining model scores does not confer physical units or meaning. |
| Pareto compromise | Six metrics are min-max normalized on the candidate set and assigned equal weights | A decision preference, not a physics result. The winner can change with candidate bounds, metrics, and weights. |
| Priority winners | Stability maximizes `flashing_score − 0.5×DWO − 0.5×pressure_index − 0.25×thermal_score`; speed/cost select the minimum corresponding score | Project-defined selection rules. The stability expression mixes differently scaled arbitrary scores and is not an accepted stability criterion. |
| Sensitivity ranking | For each variable, take the largest one-at-a-time mean fractional change over the selected endpoints/categories in flashing, DWO, and pressure scores; each fractional change divides by `max(abs(reference), 0.1)` | The metric selection, denominator floor, and endpoint range are project-defined. The ranking is not statistical sensitivity, uncertainty quantification, or a physical importance measure. |
| Percent improvement | Higher-is-better flashing score uses `(candidate − baseline)/abs(baseline)`; other metrics use `(baseline − candidate)/baseline` | This is a reporting convention applied to heuristic scores. It does not convert the scores into measured improvements; zero baselines are reported as N/A. |
| Optimizer settings | NSGA-II, population 100, 20 generations, fixed random seed | Numerical search configuration; not literature-derived physics. |
| Model scope | No BWRX-300 geometry, validated TH model, uncertainty model, or experiment-to-model validation is included | Therefore current charts and “improvement” percentages compare the heuristic equations only; they do not establish actual improvements in reactor startup. |

### What research can and cannot replace

- **Startup instability mechanisms:** cite the studies below and use them to
  choose phenomena and validation cases. Do not convert their experimental
  pressure/subcooling ranges into generic BWRX-300 limits.
- **Flashing/DWO:** Furuya et al. provide a mechanism and stability-map method
  for flashing-induced DWO in a natural-circulation BWR; Fukuda and Kobori
  provide a model-based framework for classifying two-phase instabilities.
  Implementing either requires a system-specific thermal-hydraulic model and
  validation data. Neither paper supplies the coefficients in this project's
  current score.
- **Thermal stress:** replace the ramp-rate proxy with transient structural
  analysis using temperature histories, component geometry, material data,
  boundary conditions, and fatigue/stress methodology. Generic component-fatigue
  research is a method reference, not BWRX-300 validation.
- **Operator workload and cost:** replace the hold-count multiplier only after
  defining actual operator tasks and an evidence-based human-factors measure.
  Replace the total cost score only after specifying units, economic inputs,
  and decision-maker-approved weights.
- **BWRX-300 claims:** no generic BWR experiment alone validates numerical
  startup settings for BWRX-300. A BWRX-specific model, documented inputs,
  verification, validation, and uncertainty assessment are required.

### Public research prototype path

Recent peer-reviewed work supports building a model-based research prototype,
but not by swapping published constants into the current scoring equations:

- Hurley et al. (2025) assessed TRACE for density-wave-instability onset with
  void-reactivity feedback under natural circulation. This is a relevant
  methodology reference, not proof that TRACE inputs/results or coefficients
  are available for this repository.
- Zhao, Xu, and Ishii (2025) assessed TRACE for natural-circulation BWR startup
  transients. It is a recent target for reproduction; a published paper alone
  does not supply a runnable model deck, digitized validation traces, or
  BWRX-300 validation.
- Shi et al. (2015) report startup natural-circulation instability experiments
  for a BWR-type SMR with void-reactivity feedback. These are possible
  comparison data if the actual data, experimental geometry, and conditions
  can be obtained.
- MOOSE THM is publicly available, but the public natural-circulation example
  identified for this project is single-phase. It can test integration
  plumbing; it cannot independently predict boiling instability.

Accordingly, the present code does not yet implement these papers' predictive
methods. Running the optimizer requires an explicitly configured external
simulator; without one, it reports evidence status and computes no scores. The
old heuristic can be run only with `--illustrative` or
`STARTUP_ESTIMATE_MODE=illustrative`, and its outputs are segregated. A
research prototype should only be added after a reproducible model and
comparison dataset have been selected and independently checked. Any
transferability from generic BWR experiments to BWRX-300 must be reported as
an estimate with explicit uncertainty and scale/model limitations.

Until those replacements are implemented, treat the built-in model's metrics,
Pareto ranking, winner labels, plots, and percent improvements as **illustrative
heuristic outputs only**, not research-backed performance findings.

## Peer-reviewed references

1. Aritomi, M., Chiang, J. H., Nakahashi, T., Wataru, M., & Mori, M. (1992).
   “Fundamental Study on Thermo-Hydraulics during Start-Up in Natural
   Circulation Boiling Water Reactors, (I): Thermo-Hydraulic Instabilities.”
   *Journal of Nuclear Science and Technology*, 29(7), 631–641.
   [https://doi.org/10.1080/18811248.1992.9731576](https://doi.org/10.1080/18811248.1992.9731576)
2. Subki, M. H., Aritomi, M., Watanabe, N., Chung, M. K., & Kikura, H. (2004).
   “Multi Parameters Effect on Thermohydraulic Instability in Natural
   Circulation Boiling Water Reactor during Startup.” *JSME International
   Journal Series B*, 47(2), 277–286.
   [https://doi.org/10.1299/jsmeb.47.277](https://doi.org/10.1299/jsmeb.47.277)
3. Furuya, M., Inada, F., & van der Hagen, T. H. J. J. (2005).
   “Flashing-induced density wave oscillations in a natural circulation BWR—
   mechanism of instability and stability map.” *Nuclear Engineering and
   Design*, 235(15), 1557–1569.
   [https://doi.org/10.1016/j.nucengdes.2005.01.006](https://doi.org/10.1016/j.nucengdes.2005.01.006)
4. Fukuda, K., & Kobori, T. (1979). “Classification of Two-Phase Flow
   Instability by Density Wave Oscillation Model.” *Journal of Nuclear Science
   and Technology*, 16(2), 95–108.
   [https://doi.org/10.1080/18811248.1979.9730878](https://doi.org/10.1080/18811248.1979.9730878)
5. Rudolph, J., Bergholz, S., Willuweit, A., Vormwald, M., & Bauerbach, K.
   (2011). “Methods of detailed thermal fatigue evaluation of nuclear power
   plant components.” *Materialwissenschaft und Werkstofftechnik*, 42(12),
   1082–1092.
   [https://doi.org/10.1002/mawe.201100914](https://doi.org/10.1002/mawe.201100914)
6. Gao, Q., Wang, Y., Song, F., Li, Z., & Dong, X. (2013). “Mental workload
   measurement for emergency operating procedures in digital nuclear power
   plants.” *Ergonomics*, 56(7), 1070–1085.
   [https://doi.org/10.1080/00140139.2013.790483](https://doi.org/10.1080/00140139.2013.790483)
7. Shi, S., Wu, Z., Liu, Z., Schlegel, J. P., Brooks, C. S., Eoh, J., Yan, Y.,
   Liu, Y., Yang, W. S., & Ishii, M. (2015). “Experimental study of natural
   circulation instability with void reactivity feedback during startup
   transients for a BWR-type SMR.” *Progress in Nuclear Energy*, 83, 73–81.
   [https://doi.org/10.1016/j.pnucene.2015.03.003](https://doi.org/10.1016/j.pnucene.2015.03.003)
8. Hurley, P., Liu, Y., Kozlowski, T., & Duarte, J. P. (2025). “TRACE
   assessment of density wave instability onset with void reactivity feedback
   under natural circulation.” *Nuclear Engineering and Technology*, 57,
   103195.
   [https://doi.org/10.1016/j.net.2024.08.064](https://doi.org/10.1016/j.net.2024.08.064)
9. Zhao, Y., Xu, Y., & Ishii, M. (2025). “Assessment of TRACE for predicting
   startup transients in natural circulation boiling water reactors.”
   *Nuclear Engineering and Design*, 444, 114430.
   [https://doi.org/10.1016/j.nucengdes.2025.114430](https://doi.org/10.1016/j.nucengdes.2025.114430)
10. Hansel, J., Andrs, D., Charlot, L., & Giudicelli, G. (2024). “The MOOSE
    Thermal Hydraulics Module.” *Journal of Open Source Software*, 9(94),
    6146.
    [https://doi.org/10.21105/joss.06146](https://doi.org/10.21105/joss.06146)

## Outputs and interpretation

`startup_optimization.py` writes:

- a full results table with per-candidate decision metrics
- a Pareto flag for each candidate
- a compromise score for ranking candidates
- plots showing trade-offs between startup duration, cost, and stability metrics
- profile comparison and sensitivity reports in the simulator-specific output directory

Without an external simulator, the command prints public-evidence status and
does not run the optimizer. With `--illustrative` or
`STARTUP_ESTIMATE_MODE=illustrative`, the output directory is
`results/illustrative_heuristic/`; those figures and “improvement” percentages
are heuristic score comparisons only. Historical heuristic files are kept
under `results/legacy_heuristic_outputs/` and are not current research results.

Interpretation should always consider backend validation, data quality, and assumptions behind every metric. Percent improvements are relative to the baseline values; negative startup-time or cost percentages are labeled as worsened performance. The optimizer is decision-support infrastructure, not a validated startup procedure for plant operations.

## Safety note

The project explicitly does not provide a ready-to-use startup procedure for a
reactor. Any real plant application must use approved models, validation data,
uncertainty treatment, and operational review before implementation.
