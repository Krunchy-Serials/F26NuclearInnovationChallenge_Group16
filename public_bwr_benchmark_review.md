# Public BWR Benchmark Review

## Scope and conclusion

This is a source-based review of publicly discoverable material for generic
BWR stability and startup modeling. It is not a simulation, a stability
calculation, or a prediction for BWRX-300.

The public sources reviewed do not provide, as a single downloadable package,
both a runnable BWR transient model and machine-readable Peach Bottom 2 or
Vermont Yankee low-flow density-wave benchmark measurements. Consequently, they do not support running either optimizer as a
simulator-backed Type II study in this workspace. Literature observations are
plotted below for context; no reactor-simulation results or BWRX-300
predictions are claimed.

## What the public sources provide

| Source | Publicly documented evidence | What it does not establish |
|---|---|---|
| [NUREG/CR-2998, OSTI record](https://www.osti.gov/biblio/6504608) | Describes 17 low-flow test conditions at Peach Bottom 2 and Vermont Yankee. The 1983 study used LAPUR-IV to calculate decay ratio and natural frequency of the closed-loop reactivity-to-power transfer function, compared the calculations with experimental results, and reported sensitivity to density-reactivity coefficient, recirculation-loop pressure-to-flow response, and fuel-to-cladding gap conductance. | The OSTI record has no full-text download URL or machine-readable measurement files listed. It does not identify a runnable TRACE/RELAP5 deck; the calculations described used LAPUR-IV. A benchmark summary is not enough to reproduce the calculation. |
| [Public VERA input collection](https://github.com/veracity-nuclear/vera_inputs) and [Peach Bottom 2 PB6 input](https://github.com/veracity-nuclear/vera_inputs/blob/master/BWR_Progression_Problems/2D/PB6/bwr-peach-6-00.inp) | Provides BWR Peach Bottom 2 Design 6 MPACT input cases at fixed void values (0%, 40%, and 80%), among other BWR progression cases. | The PB6 example is a static neutronics case: it sets a fixed state and explicitly turns feedback off. These inputs do not provide transient mass-flow/pressure histories or a Type II density-wave experiment. Public input files alone do not supply a runnable VERA executable. |
| [Peach Bottom 2 turbine-trip paper, OSTI record](https://www.osti.gov/biblio/2588260), [DOI](https://doi.org/10.3390/jne6030028) | The 2025 paper abstract reports a VERA simulation of a 1977 General Electric Type-4 BWR turbine-trip benchmark. It reports a simulated peak-power time of 0.75 s versus a benchmark average of 0.742 s, and a peak-power value of about 7600 MW versus a benchmark average of 7400 MW. | A turbine trip is not a startup transient or a low-flow Type II density-wave stability test. These reported values do not validate the current project's stability-index equations, and the OSTI record does not provide a verified runnable model package. |
| [NRC BWRX-300 RPV isolation and overpressure-protection report](https://www.nrc.gov/docs/ML1936/ML19364A212.pdf) and [IAEA ARIS](https://aris.iaea.org/) | Public BWRX-300 design-level and system-specific information is available. It can inform background and constrain selected design assumptions. | Design summaries and a topical safety report are not BWRX-300 startup measurements, a core/network input deck, or Type II stability validation data. |
| [NRC code overview](https://www.nrc.gov/education-regulatory-research/research/computer-codes) and [code-access requirements](https://www.nrc.gov/education-regulatory-research/research/obtaining-the-codes) | NRC identifies TRACE and RELAP5 as system thermal-hydraulics codes used for BWR/PWR analyses. U.S. academic institutions may request access through the NRC process with an NDA; the NRC page states that academic access is provided without a fee but without technical assistance. | The codes are not unrestricted downloads, and access to a code does not provide a plant-specific model, validation data, or permission to claim BWRX-300 predictive validity. |
| [MOOSE THM source](https://github.com/idaholab/moose/tree/master/modules/thermal_hydraulics) and [THM paper](https://github.com/idaholab/moose/blob/master/modules/thermal_hydraulics/joss_paper/joss_paper.md) | MOOSE is publicly accessible source code. THM is a framework for thermal-hydraulic applications using 1-D flow components. The THM paper describes the component library as primarily single-phase and identifies RELAP-7 as a separate application for two-phase light-water-reactor flow. | Building THM alone does not provide a validated BWR transient application, a BWRX-300 model, or a Type II stability benchmark. It is not installed or configured in this workspace. |
| [Fukuda & Kobori (1979), J-STAGE](https://www.jstage.jst.go.jp/article/jnst1964/16/2/16_2_95/_article) | Two density-wave instability types observed in a test loop: Type I near-zero exit steam quality (about 0–10%), where gravitational pressure drop in the unheated riser dominates; Type II at high quality (≳30%), where frictional pressure drop dominates. The paper reports inlet throttling shifts the Type II boundary to higher heating power, with no change in the Type I boundary. | The published curves are for the experiment, not BWRX-300. The plotted boundary is not a plant safety limit, and Type labels are not interchangeable with other studies' mode labels. |
| [Subki et al. (2004), J-STAGE](https://www.jstage.jst.go.jp/article/jsmeb/47/2/47_2_277/_article) | Natural-circulation startup-loop maps for 5, 10, and 15 K inlet subcooling, 0.1–0.7 MPa system pressure, and heat flux up to 577 kW/m². The paper reports mode C (in-phase hydrostatic-head oscillation) only at 0.1 MPa and 105–350 kW/m² for the 15 K map; it reports stable two-phase flow at 0.4 MPa with minimum heat flux 500 kW/m² for the 10 K map. | The 5 mm parallel-channel geometry is facility-specific. Void fraction was not measured directly; the stability regions were inferred from averaged channel flow and visual flow-pattern observations. Its C/D categories must not be relabeled as Fukuda Type I/II. |

## Technical interpretation

Decay ratio and oscillation frequency are benchmark observables used in the
NUREG/CR-2998 study. They are more physically interpretable than the current
project's 0-100 Type2 Stability Index, but reproducing them requires the
appropriate transient/frequency-domain model, documented input parameters, and
the experimental benchmark data. The report abstract's qualitative conclusion
that calculated margins agreed satisfactorily with measurements is not a
numerical dataset from which this repository can refit or validate coefficients.

The publicly available VERA PB6 input is useful as a static BWR neutronics
reference. Its fixed-void, feedback-off state cannot represent the coupled
neutronic and thermal-hydraulic oscillatory response needed for a Type II
density-wave study. The Peach Bottom turbine-trip paper is a real BWR transient
comparison, but it addresses a different event and does not supply evidence
about startup susceptibility to Type II oscillations.

Fukuda & Kobori report that higher heating power and/or system pressure
shortened oscillation period when inlet subcooling and other conditions were
held fixed. In forced-circulation tests, oscillation amplitude decreased as
system pressure and/or total flow increased. Opening the riser joint valve
(acting like a shorter riser) made Type I flow more stable and reduced its
amplitude and period; the effect on the Type II region was smaller. Their text
also says low system pressure and/or high inlet subcooling can destabilize the
initial, nearly-zero-quality stage. These are reported loop-specific
directions, not transferable numerical coefficients.

### How the new instability plots were assembled

- The Type I/II quality ranges and governing pressure-drop mechanisms are
  reproduced from Fukuda & Kobori's experimental descriptions. The Type II
  category is plotted as an open-ended lower bound (exit quality ≳30%); it is
  not treated as a complete range or a universal threshold.
- The inlet-throttling curves are approximate manual digitizations of the
  upper instability boundaries in Fukuda & Kobori's Fig. 6. The plot axes are
  the figure's inlet temperature and channel heating power. The test used
  natural circulation at 1 ata with riser A; the plotted curve labels are the
  paper's inlet-throttling coefficients 60, 120, and 400. No interpolation
  model or reactor-physics equation was fitted.
- The Subki plot uses only values stated in the paper's Fig. 10/text: for the
  15 K case, mode C occurred at 0.1 MPa over 105–350 kW/m²; for the 10 K case,
  stable two-phase flow was reported at 0.4 MPa with minimum heat flux
  500 kW/m². The 5 K, 0.2 MPa observation is described qualitatively because
  the paper does not state the transition heat-flux values in its conclusion.
  No intermediate boundaries have been inferred.
- Subki et al. used 5, 10, and 15 K subcooling, 0.1–0.7 MPa pressure, and
  heat flux up to 577 kW/m², with inlet-throttle coefficient 7.82. Their
  parallel channels had a 5 mm gap. Stability modes were assigned using
  averaged flow rates and visual flow-pattern observations, not direct void
  fraction measurement. Their in-phase mode C and density-wave mode D are
  retained as named in that paper; neither is relabeled as Fukuda Type I or
  Type II.

## Figures and what they support

Run `python plot_public_bwr_evidence.py` to generate six figures under
`results/literature_evidence/`:

- `peach_bottom_turbine_trip_comparison.png` plots only the two benchmark
  average / VERA values stated in the 2025 paper's public abstract: peak-power
  time (0.742 s / 0.75 s) and peak power (7400 MW / approximately 7600 MW).
  The plot annotates relative differences of about 1.08% and 2.70%. These
  differences describe those reported values only; the abstract reports no
  uncertainty bars, and turbine-trip agreement does not establish startup or
  Type II density-wave prediction.
- `public_evidence_coverage_matrix.png` distinguishes directly reported
  evidence from related evidence and information not reported in the reviewed
  sources. The categories are qualitative, not scores. In particular, the
  NUREG/CR-2998 record reports a generic-BWR stability comparison, while the
  reviewed sources do not supply the complete runnable-data package or
  BWRX-300 validation.
- `predictive_evidence_gates.png` shows the evidence needed to move from a
  literature reference to a target-reactor prediction. Only the literature
  reference stage is marked available based on the sources reviewed; this
  figure is a workflow/evidence-status diagram, not measured performance.
- `fukuda_type_quality_bands.png` displays the experimental exit-quality
  ranges used to distinguish Fukuda & Kobori's Type I and Type II instabilities
  and the corresponding dominant pressure-drop mechanisms. The open-ended
  Type II arrow indicates a lower-bound description (≳30%), not a fully mapped
  unstable range.
- `fukuda_type_ii_throttle_boundary.png` redraws the high-power instability
  boundaries in Fukuda & Kobori's Fig. 6 for inlet-throttling coefficients
  60, 120, and 400. Coordinates are approximate manual digitizations of the
  published curves, not tabulated measurements. The figure shows the paper's
  reported trend: increasing inlet throttling shifts the Type II boundary to
  higher heating power, while the paper says the Type I boundary is unchanged.
  It applies to their natural-circulation loop at 1 ata with riser A.
- `subki_startup_stability_observations.png` plots numeric observations
  reported from Subki et al.'s startup maps: the mode-C heat-flux interval at
  0.1 MPa and the reported 10 K stable-flow point at 0.4 MPa and 500 kW/m².
  The 5 K finding is stated qualitatively because the paper does not provide
  numeric transition thresholds in that text. Mode C (hydrostatic-head
  oscillation) and mode D (density-wave oscillation) are preserved as that
  paper names them, not equated with Fukuda's Type I and Type II.

Together, the figures support literature-grounded qualitative trends: greater
inlet throttling moved the Type II boundary to higher heating power in Fukuda
and Kobori's test loop; riser length is reported to matter more for Type I;
and Subki et al.'s startup-loop maps show the observed stability regions vary
with pressure and subcooling. They do not establish quantitative trends for a
generic commercial BWR or BWRX-300. The evidence is not enough to run or
validate the scripts as predictors of startup or Type II stability.

In plain terms: these graphs show real trends observed in small experimental
loops, not reactor predictions. More inlet throttling moved one measured Type
II boundary to higher power; lower subcooling/pressure combinations changed
which flow regimes were observed in another startup loop. The geometry and
scale are different from BWRX-300, and the underlying data are not a complete
runnable reactor model. Do not use these plots to set operating conditions.

## Current repository and run status

- `startup_optimization.py` can call an external simulator only when a backend
  is configured. Its built-in heuristic mode is an explicit workflow demo,
  not literature-derived physics.
- The repository's MOOSE adapter requires a user-supplied executable and model
  deck. Its metric extraction hooks intentionally raise `NotImplementedError`
  until validated metrics are implemented.
- No TRACE, RELAP5, MOOSE executable, simulator environment configuration, or
  relevant transient input deck was present in the workspace when this review
  was prepared.
- `type2_stability_analysis.py` now prints the evidence status by default. Its
  `--illustrative` option still prints the project's assumption-based example;
  it must not be represented as a literature result or prediction.

## Defensible next steps

1. For a reproducible generic-BWR stability calculation, obtain authorized
   TRACE/RELAP5 access through the NRC process or another validated simulator
   with appropriate two-phase and feedback capabilities.
2. Obtain the underlying Peach Bottom 2/Vermont Yankee low-flow benchmark
   input models and measurement/uncertainty data, citing NUREG/CR-2998 when
   requesting them from NRC/CAMP or the report provider.
3. Reproduce the published decay-ratio/frequency comparisons before changing
   the current score equations; reserve an independent condition for validation.
4. Keep any transfer to BWRX-300 explicitly unvalidated until BWRX-specific
   geometry, design inputs, operating procedures, and applicable validation
   observations are available.

## Sources

- March-Leuba, J. and Otaduy, P. J. (1983), *Comparison of BWR-stability
  measurements with calculations using the code LAPUR-IV*, NUREG/CR-2998,
  [OSTI record](https://www.osti.gov/biblio/6504608).
- Herring, N., Salko, R., and Asgari, M. (2025), *A High-Fidelity Model of the
  Peach Bottom 2 Turbine-Trip Benchmark Using VERA*, [OSTI record](https://www.osti.gov/biblio/2588260),
  [DOI](https://doi.org/10.3390/jne6030028).
- Fukuda, K. and Kobori, T. (1979), *Classification of Two-Phase Flow
  Instability by Density Wave Oscillation Model*, Journal of Nuclear Science
  and Technology, 16(2), 95–108, [J-STAGE article](https://www.jstage.jst.go.jp/article/jnst1964/16/2/16_2_95/_article).
- Subki, M.H., Aritomi, M., Watanabe, N. and Muncharoen, S. (2004),
  *Multi Parameters Effect on Thermohydraulic Instability in Natural
  Circulation Boiling Water Reactor during Startup*, JSME International
  Journal Series B, 47(2), 277–284,
  [DOI](https://doi.org/10.1299/jsmeb.47.277),
  [J-STAGE article](https://www.jstage.jst.go.jp/article/jsmeb/47/2/47_2_277/_article).
- [NRC thermal-hydraulics code overview](https://www.nrc.gov/education-regulatory-research/research/computer-codes).
- [NRC code-access instructions](https://www.nrc.gov/education-regulatory-research/research/obtaining-the-codes).
- [Public VERA input collection](https://github.com/veracity-nuclear/vera_inputs).
- [MOOSE THM module](https://github.com/idaholab/moose/tree/master/modules/thermal_hydraulics)
  and [THM paper source](https://github.com/idaholab/moose/blob/master/modules/thermal_hydraulics/joss_paper/joss_paper.md).
- [BWRX-300 RPV isolation and overpressure-protection topical report](https://www.nrc.gov/docs/ML1936/ML19364A212.pdf).
- [IAEA Advanced Reactors Information System](https://aris.iaea.org/).
