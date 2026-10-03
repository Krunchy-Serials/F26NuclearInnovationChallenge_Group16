# MOOSE THM Startup Backend

This package connects the startup optimizer to an existing, user-owned MOOSE
Thermal Hydraulics Module (THM) transient model. It renders a supplied model deck,
launches the configured MOOSE application, parses a CSV transient table, and
passes the parsed data to explicit metric-extraction hooks.

**This repository does not include a BWRX-300 MOOSE model, validated startup
procedure, THM correlations, structural model, or fuel-cycle cost model.** The
engineering metric extractors intentionally raise `NotImplementedError`.
Do not use optimizer output as a plant procedure. Implement and validate the
metric hooks with the applicable model, data, uncertainty treatment, and review
before running a study.

## 1. Required MOOSE Installation

Install and build the MOOSE framework and the THM application/model using the
current official MOOSE installation instructions for your platform. The
executable configured below must be the compiled application that contains the
THM objects used by your supplied input template. This package does not install
or build MOOSE.

Install Python dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

Set the required backend variables:

```bash
export MOOSE_EXECUTABLE=/path/to/your/thm-app-opt
export MOOSE_INPUT_TEMPLATE=/path/to/your/model/startup_template.i
export MOOSE_COMPLETION_POWER=1.0
```

`MOOSE_COMPLETION_POWER` uses the units of the configured CSV power column. For
a normalized power column, `1.0` means the user-defined full-power value; for an
MW column, set it to the model's rated-power value. This is a data threshold, not
a recommended operating target.

Optional settings:

- `MOOSE_RUN_DIRECTORY`: root for per-candidate run directories; defaults to
  `moose_runs/`.
- `MOOSE_OUTPUT_CSV`: combined transient CSV filename; defaults to
  `startup_out.csv`.
- `MOOSE_TIME_COLUMN`, `MOOSE_POWER_COLUMN`, `MOOSE_PRESSURE_COLUMN`,
  `MOOSE_VOID_FRACTION_COLUMN`, `MOOSE_MASS_FLOW_COLUMN`,
  `MOOSE_FLUID_TEMPERATURE_COLUMN`, `MOOSE_CLADDING_TEMPERATURE_COLUMN`:
  emitted CSV column names.
- `MOOSE_TIME_UNIT`: `s`, `min`, or `h`; defaults to `s`.
- `MOOSE_TIMEOUT_SECONDS`: per-run timeout; defaults to 3600.
- `MOOSE_EXTRA_ARGUMENTS`: additional executable arguments, parsed without a
  shell.
- `MOOSE_MPI_LAUNCHER`: optional launcher prefix such as `mpiexec -n 4`.

## 2. Simulation Workflow

The startup optimizer loads the factory through:

```bash
export STARTUP_SIMULATOR=backend.moose_thm:create_simulator
python startup_optimization.py
```

For each NSGA-II candidate, the adapter:

1. Converts the optimizer's `StartupProcedure` to the backend input contract.
2. Creates a unique run directory.
3. Renders the user's MOOSE deck template and writes a hold-schedule JSON sidecar.
4. Executes the configured application as `executable [MPI/extra args] -i startup.i`.
5. Saves stdout/stderr, checks the process exit status, and parses the configured
   transient CSV.
6. Extracts startup time from the configured power-threshold crossing.
7. Calls hooks for flashing margin, DWO index, pressure-oscillation index,
   thermal stress, and the three startup-cost components.
8. Returns a mapping that the existing `MOOSETHMAdapter` validates as
   `SimulationMetrics`.

NSGA-II cannot complete until every placeholder hook has a validated
implementation. This is intentional: the backend never invents a score when the
simulation data or validated metric method is missing.

## 3. Input Deck Generation

`input_generator.py` requires a model-specific MOOSE `.i` template containing
all of these exact tokens:

- `{{POWER_RAMP_RATE}}`
- `{{PRESSURE_RAMP_RATE}}`
- `{{BOILING_INITIATION_PRESSURE}}`
- `{{INLET_SUBCOOLING}}`
- `{{STARTUP_TYPE}}`
- `{{INITIAL_PRESSURE_MPA}}`
- `{{INITIAL_TEMPERATURE_C}}`
- `{{HOLD_COUNT}}`
- `{{HOLD_DURATION}}`
- `{{HOLD_SCHEDULE_JSON}}`
- `{{HOLD_SCHEDULE_FILE}}`
- `{{OUTPUT_CSV}}`

The renderer also provides `{{HOLD_1_POWER}}`, `{{HOLD_1_DURATION}}` through
`{{HOLD_3_POWER}}`, and `{{HOLD_3_DURATION}}`. The optimizer currently assigns
one duration to all points in a hold schedule. Missing holds are set to zero.
The hold schedule is serialized as JSON in the run folder. The selected `COLD`,
`WARM`, or `HOT` startup type and its initial pressure/temperature are also
passed to the deck. These type conditions are illustrative placeholders, not
BWRX-300 data. The template must consume the tokens using syntax and controls
implemented by your own MOOSE model; this package cannot make a generic THM
deck physically complete.

A template must already define the reactor/network geometry, components,
materials, closures, boundary and initial conditions, power/pressure controls,
transient executioner, and CSV output. Only the application owner can validate
that the template applies each requested parameter correctly.

## 4. Output Parsing

`parser.py` reads one combined CSV table using pandas. It requires configured
time and power columns, verifies finite numeric values and nondecreasing time,
and retains the original data and source path. Configure column names to match
the model's `CSV`/postprocessor output. If the model emits separate CSV files,
combine the required outputs into one table in the model or implement a
model-specific parser extension.

Startup time is interpolated at the first crossing of `MOOSE_COMPLETION_POWER`
and converted using `MOOSE_TIME_UNIT`. If the trace does not reach the configured
threshold, the run is rejected.

## 5. Expected Transient Outputs

At minimum, provide time and power histories for startup-time extraction. The
metric hooks document the additional data expected:

- **Flashing margin:** local pressure, fluid temperature or enthalpy, vapor
  quality or void fraction, and mass flow, with a documented sign and units.
- **Density-wave oscillation index:** adequately sampled pressure-drop,
  mass-flow, void/quality, and power histories for a validated method.
- **Pressure-oscillation index:** pressure histories and documented signal
  processing, sampling, and units.
- **Thermal stress:** preferably coupled structural-solver stress output. THM
  temperatures and pressures alone need geometry, constraints, and material
  properties before stress can be established.
- **Startup cost:** the sum of lost-generation index,
  operator-intervention index, and thermal-stress penalty. Each term needs an
  approved method and consistent scaling; the optimizer does not define a
  plant cost or currency model.

The built-in estimate mode uses 0.4 MPa and 0.7 MPa threshold adjustments as
explicit illustrative assumptions. The code does not independently verify
their experimental basis. Backend metrics must document their own definitions,
units, and validity. Preserve enough time/location metadata to audit peak
metrics.

## 6. Future OpenFOAM / GeN-Foam Integration

Implement a runner with the same callable shape as `MOOSETHMAdapter`: accept the
serialized procedure, generate a solver-specific case from a validated template,
execute OpenFOAM/GeN-Foam, parse its time directories and fields, and return the
new metric contract (`flashing_margin`, `density_wave_oscillation_index`,
`pressure_oscillation_index`, `thermal_stress`, plus the three startup-cost
components). Wire it to the existing `OpenFOAMGeNFoamAdapter`; leave
`startup_optimization.py` unchanged. Keep solver-specific mesh, boundary,
closure, convergence, and unit checks inside that backend.

## 7. Future OpenMC Coupling

Implement an `OpenMCPhysicsAdapter` provider that returns documented neutronics
inputs, such as spatial power distributions or uncertainty data, from a
validated OpenMC calculation. Pass those fields to a coupled MOOSE/OpenFOAM
runner through `CoupledStartupSimulator`. Define data mapping, normalization,
uncertainty propagation, and convergence between physics and THM explicitly.
OpenMC outputs alone do not provide transient instability risk, structural
stress, or startup cost.
