"""Create evidence-coverage figures from the cited public BWR literature review.

The figures distinguish reported benchmark values from evidence gaps; they do
not calculate reactor physics or infer BWRX-300 operating performance.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


COLORS = {
    "ink": "#203040",
    "blue": "#356A8A",
    "teal": "#2A7F78",
    "green": "#4C956C",
    "amber": "#E9B44C",
    "red": "#C8553D",
    "light": "#F4F7F8",
    "muted": "#62727B",
}


def plot_turbine_trip_comparison(output_path: Path) -> None:
    """Plot the two Peach Bottom 2 values reported in the 2025 paper abstract."""
    metrics = (
        ("Peak-power time", 0.742, 0.75, "s", "Benchmark average", "VERA"),
        ("Peak power", 7400.0, 7600.0, "MW", "Benchmark average", "VERA"),
    )
    figure, axes = plt.subplots(1, 2, figsize=(12, 5.7))
    figure.suptitle(
        "Peach Bottom 2 turbine-trip: paper-reported benchmark comparison",
        fontsize=15,
        fontweight="bold",
        color=COLORS["ink"],
        y=0.98,
    )

    for axis, (title, benchmark, vera, unit, benchmark_label, vera_label) in zip(
        axes, metrics, strict=True
    ):
        bars = axis.bar(
            (benchmark_label, vera_label),
            (benchmark, vera),
            color=(COLORS["blue"], COLORS["amber"]),
            width=0.58,
            zorder=3,
        )
        axis.set_title(title, fontweight="bold", color=COLORS["ink"], pad=12)
        axis.set_ylabel(unit)
        axis.grid(axis="y", alpha=0.22, zorder=0)
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(axis="x", labelsize=9)
        for bar, value in zip(bars, (benchmark, vera), strict=True):
            axis.annotate(
                f"{value:g} {unit}",
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 7),
                textcoords="offset points",
                ha="center",
                fontsize=10,
                fontweight="bold",
                color=COLORS["ink"],
            )
        relative_difference = (vera - benchmark) / benchmark * 100
        axis.text(
            0.5,
            0.87,
            f"VERA vs benchmark average: {relative_difference:+.2f}%",
            transform=axis.transAxes,
            ha="center",
            color=COLORS["ink"],
            fontsize=9,
            bbox={"boxstyle": "round,pad=0.35", "fc": COLORS["light"], "ec": "none"},
        )
        axis.set_ylim(0, max(benchmark, vera) * 1.28)

    figure.text(
        0.5,
        0.12,
        "Source: Herring et al. (2025), OSTI 2588260 / doi:10.3390/jne6030028. "
        "Values reproduced from the public abstract; no uncertainty bars were "
        "reported there.",
        ha="center",
        fontsize=8.5,
        color=COLORS["muted"],
        wrap=True,
    )
    figure.text(
        0.5,
        0.055,
        "This is a turbine-trip result, not a startup or Type II density-wave "
        "benchmark, and not BWRX-300 validation.",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color=COLORS["red"],
    )
    figure.tight_layout(rect=(0.03, 0.17, 0.97, 0.93))
    figure.savefig(output_path, dpi=190, bbox_inches="tight")
    plt.close(figure)


def plot_evidence_matrix(output_path: Path) -> None:
    """Show which claims the reviewed public sources do and do not support."""
    rows = (
        "NUREG/CR-2998\nPB2 + Vermont Yankee",
        "VERA PB6 inputs\nPeach Bottom 2",
        "VERA PB2 turbine-trip\n2025 paper",
        "BWRX-300 design\nNRC / IAEA sources",
    )
    columns = (
        "Generic-BWR\nstability evidence",
        "Startup-transient\nevidence",
        "Runnable relevant\nmodel + data",
        "BWRX-300\nstability validation",
    )
    # 2 = reported for the specific column; 1 = related, but not sufficient;
    # 0 = not reported in the reviewed source. These are categorical, not scores.
    evidence = (
        (2, 0, 1, 0),
        (0, 0, 1, 0),
        (0, 1, 1, 0),
        (0, 1, 0, 1),
    )
    cell_text = (
        ("Reported\nlow-flow tests", "Not in source", "LAPUR-IV cited;\npackage not located", "Not BWRX data"),
        ("Static case;\nnot DWO", "Not transient", "Static MPACT\ninputs only", "Not BWRX data"),
        ("Different event;\nnot DWO", "Turbine trip;\nnot startup", "Paper results;\ncase not verified", "Not BWRX data"),
        ("No stability\ndata in reviewed docs", "Design context;\nnot startup data", "No relevant\ndeck located", "Design info;\nnot validation"),
    )
    color_map = ListedColormap(("#F5D8D2", "#F6E8C3", "#D6EADF"))

    figure, axis = plt.subplots(figsize=(14, 7.5))
    figure.suptitle(
        "What the reviewed public sources actually support",
        fontsize=16,
        fontweight="bold",
        color=COLORS["ink"],
        y=0.98,
    )
    axis.imshow(evidence, cmap=color_map, vmin=0, vmax=2, aspect="auto")
    axis.set_xticks(range(len(columns)), labels=columns, fontsize=9)
    axis.set_yticks(range(len(rows)), labels=rows, fontsize=9)
    axis.tick_params(axis="both", length=0, pad=10)
    axis.set_xticks([index - 0.5 for index in range(1, len(columns))], minor=True)
    axis.set_yticks([index - 0.5 for index in range(1, len(rows))], minor=True)
    axis.grid(which="minor", color="white", linewidth=3)
    axis.tick_params(which="minor", bottom=False, left=False)
    for spine in axis.spines.values():
        spine.set_visible(False)

    for row_index, row in enumerate(cell_text):
        for column_index, text in enumerate(row):
            color = COLORS["ink"] if evidence[row_index][column_index] else "#73564F"
            axis.text(
                column_index,
                row_index,
                text,
                ha="center",
                va="center",
                fontsize=8.4,
                color=color,
                linespacing=1.25,
            )

    legend = (
        ("Reported for this question", "#D6EADF"),
        ("Related, but not sufficient", "#F6E8C3"),
        ("Not reported in reviewed source", "#F5D8D2"),
    )
    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="s",
            linestyle="",
            markersize=11,
            markerfacecolor=color,
            markeredgecolor="white",
            label=label,
        )
        for label, color in legend
    ]
    axis.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.20),
        ncol=3,
        frameon=False,
        fontsize=8.5,
    )
    figure.text(
        0.5,
        0.035,
        "“Not reported” means absent from the specific sources reviewed, not "
        "proof that the information does not exist elsewhere. See "
        "public_bwr_benchmark_review.md for source links.",
        ha="center",
        fontsize=8,
        color=COLORS["muted"],
    )
    figure.tight_layout(rect=(0.02, 0.11, 0.98, 0.91))
    figure.savefig(output_path, dpi=190, bbox_inches="tight")
    plt.close(figure)


def plot_prediction_evidence_gates(output_path: Path) -> None:
    """Illustrate missing evidence gates between literature and plant prediction."""
    stages = (
        (
            "1. Literature\nreference",
            "AVAILABLE",
            "Published generic-BWR\nstability comparisons",
            COLORS["green"],
        ),
        (
            "2. Traceable data",
            "GAP",
            "Per-condition measurements,\nuncertainties, metadata",
            COLORS["red"],
        ),
        (
            "3. Runnable model",
            "GAP",
            "Compatible solver, input deck,\nreproducible settings",
            COLORS["red"],
        ),
        (
            "4. Independent\nreproduction",
            "GAP",
            "Match benchmark outcomes;\nreport errors and uncertainty",
            COLORS["red"],
        ),
        (
            "5. BWRX-300\ntransfer",
            "GAP",
            "BWRX-specific inputs and\napplicable validation evidence",
            COLORS["red"],
        ),
    )
    figure, axis = plt.subplots(figsize=(15, 5.8))
    axis.set_xlim(0, 15)
    axis.set_ylim(0, 5.8)
    axis.axis("off")
    figure.suptitle(
        "Evidence gates for a predictive reactor claim",
        fontsize=16,
        fontweight="bold",
        color=COLORS["ink"],
        y=0.97,
    )
    x_positions = (0.25, 3.2, 6.15, 9.1, 12.05)
    box_width, box_height, box_y = 2.55, 2.35, 2.15
    for index, ((title, status, detail, color), x_position) in enumerate(
        zip(stages, x_positions, strict=True)
    ):
        box = FancyBboxPatch(
            (x_position, box_y),
            box_width,
            box_height,
            boxstyle="round,pad=0.08,rounding_size=0.12",
            facecolor="#EFF6F1" if status == "AVAILABLE" else "#FBEEEB",
            edgecolor=color,
            linewidth=2,
        )
        axis.add_patch(box)
        axis.text(
            x_position + box_width / 2,
            box_y + 1.82,
            title,
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=COLORS["ink"],
        )
        axis.text(
            x_position + box_width / 2,
            box_y + 1.23,
            status,
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color=color,
        )
        axis.text(
            x_position + box_width / 2,
            box_y + 0.58,
            detail,
            ha="center",
            va="center",
            fontsize=8,
            color=COLORS["ink"],
            linespacing=1.3,
        )
        if index < len(stages) - 1:
            axis.add_patch(
                FancyArrowPatch(
                    (x_position + box_width + 0.06, box_y + box_height / 2),
                    (x_positions[index + 1] - 0.08, box_y + box_height / 2),
                    arrowstyle="-|>",
                    mutation_scale=12,
                    linewidth=1.5,
                    color=COLORS["muted"],
                )
            )
    axis.text(
        7.5,
        1.22,
        "A literature citation is a starting point—not a substitute for the "
        "data, executable model, reproduction, and target-reactor validation.",
        ha="center",
        fontsize=10,
        color=COLORS["ink"],
        wrap=True,
    )
    axis.text(
        7.5,
        0.55,
        "Current evidence status is based on the sources reviewed in "
        "public_bwr_benchmark_review.md; it is not an exhaustive search of "
        "private or restricted material.",
        ha="center",
        fontsize=8,
        color=COLORS["muted"],
        wrap=True,
    )
    figure.savefig(output_path, dpi=190, bbox_inches="tight")
    plt.close(figure)


def plot_fukuda_type_ii_throttle_boundary(output_path: Path) -> None:
    """Redraw the approximate Type II threshold curves from Fukuda & Kobori Fig. 6."""
    curves = {
        "K_in = 60": (
            (62, 450), (69, 555), (76, 625), (83, 645), (91, 610), (100, 530)
        ),
        "K_in = 120": (
            (63, 735), (69, 805), (76, 825), (84, 790), (92, 720), (99, 650)
        ),
        "K_in = 400": (
            (51, 920), (57, 1040), (65, 1090), (73, 1115), (78, 1100),
            (86, 1035), (94, 930), (100, 845)
        ),
    }
    colors = (COLORS["blue"], COLORS["teal"], COLORS["red"])
    figure, axis = plt.subplots(figsize=(10, 6.5))
    for (label, points), color in zip(curves.items(), colors, strict=True):
        inlet_temperature, channel_power = zip(*points, strict=True)
        axis.plot(
            inlet_temperature,
            channel_power,
            marker="o",
            markersize=3.5,
            linewidth=2,
            color=color,
            label=label,
        )

    axis.set_xlim(48, 102)
    axis.set_ylim(350, 1220)
    axis.set_xlabel("Inlet temperature (°C)")
    axis.set_ylabel("Channel heating power (kW)")
    axis.grid(alpha=0.22)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(title="Inlet-throttling coefficient", frameon=False, loc="lower right")
    axis.set_title(
        "Inlet throttling shifts the Type II instability boundary",
        fontsize=14,
        fontweight="bold",
        color=COLORS["ink"],
        pad=12,
    )
    axis.text(
        0.02,
        0.97,
        "Natural-circulation loop, P = 1 ata, riser A",
        transform=axis.transAxes,
        va="top",
        fontsize=9,
        color=COLORS["muted"],
    )
    figure.text(
        0.5,
        0.035,
        "Approximate manual read-off of the instability-boundary curves in "
        "Fukuda & Kobori (1979), Fig. 6; points are digitized estimates, not "
        "tabulated measurements. The paper reports the high-power boundary as "
        "Type II and says greater inlet throttling moves it to higher power; "
        "the Type I boundary does not change. Not a BWR/BWRX-300 operating limit.",
        ha="center",
        fontsize=8.5,
        color=COLORS["muted"],
        wrap=True,
    )
    figure.tight_layout(rect=(0.04, 0.12, 0.98, 0.95))
    figure.savefig(output_path, dpi=190, bbox_inches="tight")
    plt.close(figure)


def plot_fukuda_type_quality_bands(output_path: Path) -> None:
    """Show Fukuda & Kobori's reported exit-quality ranges and mechanisms."""
    figure, axis = plt.subplots(figsize=(11, 5.4))
    axis.barh(
        1,
        10,
        left=0,
        height=0.42,
        color=COLORS["blue"],
        edgecolor="white",
        label="Reported Type I range",
    )
    axis.annotate(
        "Low exit quality: about 0–10%\nGravitational pressure drop in the\nunheated riser is dominant",
        xy=(5, 1),
        xytext=(14, 1.45),
        arrowprops={"arrowstyle": "->", "color": COLORS["muted"]},
        fontsize=9,
        color=COLORS["ink"],
    )
    axis.annotate(
        "High exit quality: ≳30%\nFrictional pressure drop in heated\nchannel/riser is dominant",
        xy=(32, 0),
        xytext=(45, 0.5),
        arrowprops={"arrowstyle": "->", "color": COLORS["muted"]},
        fontsize=9,
        color=COLORS["ink"],
    )
    axis.annotate(
        "",
        xy=(97, 0),
        xytext=(30, 0),
        arrowprops={"arrowstyle": "-|>", "color": COLORS["red"], "lw": 8},
    )
    axis.set_yticks((0, 1), labels=("Type II", "Type I"))
    axis.set_xlim(0, 100)
    axis.set_ylim(-0.45, 1.85)
    axis.set_xlabel("Exit steam quality, xₑ (%)")
    axis.grid(axis="x", alpha=0.2)
    axis.set_axisbelow(True)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.tick_params(axis="y", length=0, pad=10)
    axis.set_title(
        "Type I and Type II are distinct density-wave instability regimes",
        fontsize=14,
        fontweight="bold",
        color=COLORS["ink"],
        pad=14,
    )
    figure.text(
        0.5,
        0.035,
        "Source: Fukuda & Kobori (1979), experimental classification. The "
        "Type II arrow means xₑ ≳30% (a reported lower bound), not that every "
        "quality up to 100% is unstable. The 10–30% gap is not classified by "
        "these two observed types in the cited description.",
        ha="center",
        fontsize=8.5,
        color=COLORS["muted"],
        wrap=True,
    )
    figure.tight_layout(rect=(0.04, 0.12, 0.98, 0.93))
    figure.savefig(output_path, dpi=190, bbox_inches="tight")
    plt.close(figure)


def plot_subki_startup_observations(output_path: Path) -> None:
    """Plot reported numeric observations from Subki et al.'s startup-loop maps."""
    figure, axis = plt.subplots(figsize=(10, 6.5))
    axis.vlines(
        0.1,
        105,
        350,
        color=COLORS["amber"],
        linewidth=5,
        alpha=0.75,
        label="In-phase hydrostatic-head oscillation (mode C)",
    )
    axis.scatter(
        (0.4,),
        (500,),
        color=COLORS["green"],
        edgecolor="white",
        linewidth=0.8,
        s=115,
        marker="D",
        zorder=4,
        label="Stable two-phase flow reported",
    )
    axis.annotate(
        "ΔTsub = 15 K\nmode C observed only at 0.1 MPa\nq″ = 105–350 kW/m²",
        xy=(0.1, 350),
        xytext=(0.19, 410),
        arrowprops={"arrowstyle": "->", "color": COLORS["muted"]},
        fontsize=9,
        color=COLORS["ink"],
    )
    axis.annotate(
        "ΔTsub = 10 K\nminimum reported heat flux\nfor stable two-phase flow",
        xy=(0.4, 500),
        xytext=(0.53, 520),
        arrowprops={"arrowstyle": "->", "color": COLORS["muted"]},
        fontsize=9,
        color=COLORS["ink"],
    )
    axis.text(
        0.98,
        0.48,
        "At ΔTsub = 5 K and 0.2 MPa:\nstable two-phase flow was observed\nat relatively low heat flux, but\nDWO returned at higher heat flux.\nThe paper does not state numeric\nthresholds for these transitions.",
        transform=axis.transAxes,
        ha="right",
        va="center",
        fontsize=8.5,
        color=COLORS["ink"],
        bbox={"boxstyle": "round,pad=0.5", "fc": COLORS["light"], "ec": "#D2DDE1"},
    )
    axis.set_xlim(0.05, 0.75)
    axis.set_ylim(80, 570)
    axis.set_xlabel("System pressure (MPa)")
    axis.set_ylabel("Heat flux (kW/m²)")
    axis.set_xticks((0.1, 0.2, 0.4, 0.5, 0.7))
    axis.grid(alpha=0.22)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, loc="upper left", fontsize=8)
    axis.set_title(
        "Startup-loop observations vary with subcooling and pressure",
        fontsize=14,
        fontweight="bold",
        color=COLORS["ink"],
        pad=12,
    )
    figure.text(
        0.5,
        0.035,
        "Source: Subki et al. (2004), Fig. 10 and conclusions. Tested parallel "
        "channel gap: 5 mm; inlet throttle coefficient K_in = 7.82. Mode C is "
        "hydrostatic-head oscillation, not Fukuda & Kobori Type I; the paper's "
        "mode D is called density-wave oscillation but is not mapped to Type II. "
        "Generic laboratory evidence only, not BWRX-300.",
        ha="center",
        fontsize=8.5,
        color=COLORS["muted"],
        wrap=True,
    )
    figure.tight_layout(rect=(0.04, 0.12, 0.98, 0.95))
    figure.savefig(output_path, dpi=190, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/literature_evidence"),
        help="Directory for generated PNG figures.",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    plot_turbine_trip_comparison(
        args.output_dir / "peach_bottom_turbine_trip_comparison.png"
    )
    plot_evidence_matrix(args.output_dir / "public_evidence_coverage_matrix.png")
    plot_prediction_evidence_gates(
        args.output_dir / "predictive_evidence_gates.png"
    )
    plot_fukuda_type_ii_throttle_boundary(
        args.output_dir / "fukuda_type_ii_throttle_boundary.png"
    )
    plot_fukuda_type_quality_bands(
        args.output_dir / "fukuda_type_quality_bands.png"
    )
    plot_subki_startup_observations(
        args.output_dir / "subki_startup_stability_observations.png"
    )
    print(f"Generated six literature-evidence figures in {args.output_dir}/")


if __name__ == "__main__":
    main()
