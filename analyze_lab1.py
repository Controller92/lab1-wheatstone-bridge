#!/usr/bin/env python3
"""Wheatstone bridge analysis.

Run:
    python analyze_lab1.py
    python analyze_lab1.py --help

Default output is provisional because instrument uncertainty inputs
have not been established.

The default RSS-of-limits convention uses the confirmed 1% reference
tolerance directly. It is an engineering estimate, not a standard
uncertainty or a 95% interval.

Use --convention rectangular-standard to convert independent rectangular
limits to standard uncertainties by dividing each limit by sqrt(3).
"""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
import json
import math
import os
from pathlib import Path
import tempfile

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "lab1-mpl-cache")
)

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np


# Experimental inputs
# Resistances are nominal labeled values, not independently measured values.
# The classroom example and initial bridge-balance row are excluded.
NOMINAL_KOHM = np.array([
    4., 6., 8., 10., 12., 14., 16., 18., 20.
])

DELTA_V = np.array([
    2.511, 1.648, 1.01, 0.45, 0.002,
    -0.39, -0.72, -1.01, -1.27
])

REFERENCE_KOHM = 12.0
SUPPLY_V = 10.0
TOLERANCE = 0.01

SOURCE_DESCRIPTION = "User-supplied Lab 1 measurements embedded in this script."

BLUE = "#215A8A"
ORANGE = "#BD6B25"
GRAY = "#596570"


def resistance(r, s, d):
    """Return resistance in kohm.

    r: reference resistance in kohm
    s: supply voltage in V
    d: differential voltage in V, defined as Vleft - Vright
    """
    denominator = np.asarray(s + 2 * d)

    if np.any(np.isclose(
        denominator, 0, atol=1e-12, rtol=0
    )):
        raise ValueError(
            "Bridge inversion is singular at Vs + 2*dV = 0."
        )

    return r * (s - 2 * d) / denominator


def sensitivities(r, s, d):
    """Return partial derivatives with respect to R, Vs, and dV."""
    denominator = s + 2 * d

    derivative_r = (s - 2 * d) / denominator
    derivative_s = 4 * r * d / denominator**2
    derivative_d = -4 * r * s / denominator**2

    return derivative_r, derivative_s, derivative_d


def reported(value, uncertainty, sig=2):
    """Format a value and uncertainty with matching decimal positions.

    Uncertainty is rounded to the requested significant figures.
    Decimal ROUND_HALF_UP is used only for reporting.
    Calculations retain full precision.

    A carry across a power of ten is handled explicitly:
    0.09996 becomes 0.10 when two significant figures are requested.
    """
    if (
        not math.isfinite(value)
        or not math.isfinite(uncertainty)
        or uncertainty <= 0
    ):
        raise ValueError(
            "Reporting requires a finite value and positive uncertainty."
        )

    u = Decimal(str(uncertainty))

    quantum = Decimal(10) ** (u.adjusted() - sig + 1)
    rounded_u = u.quantize(
        quantum, rounding=ROUND_HALF_UP
    )

    quantum = Decimal(10) ** (
        rounded_u.adjusted() - sig + 1
    )
    rounded_u = u.quantize(
        quantum, rounding=ROUND_HALF_UP
    )

    rounded_value = Decimal(str(value)).quantize(
        quantum, rounding=ROUND_HALF_UP
    )

    places = max(0, -quantum.adjusted())

    value_string = f"{rounded_value:.{places}f}"
    uncertainty_string = f"{rounded_u:.{places}f}"

    combined = (
        f"{value_string} ± {uncertainty_string}"
    )

    return value_string, uncertainty_string, combined


def nonnegative(text):
    """Validate a nonnegative command-line input."""
    value = float(text)

    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError(
            "Use a finite nonnegative number."
        )

    return value


def parser():
    argument_parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    argument_parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "results"
    )

    argument_parser.add_argument(
        "--supply-limit-v",
        type=nonnegative,
        default=None,
        help=(
            "Assigned supply half-width in V. "
            "Unknown by default, not assumed exact."
        )
    )

    argument_parser.add_argument(
        "--meter-percent",
        type=nonnegative,
        default=None,
        help=(
            "Assigned meter percentage of absolute reading. "
            "For example, 0.1 means 0.1 percent."
        )
    )

    argument_parser.add_argument(
        "--meter-absolute-v",
        type=nonnegative,
        default=None,
        help=(
            "Additional meter half-width in V, including "
            "counts or resolution as appropriate."
        )
    )

    argument_parser.add_argument(
        "--balance-limit-v",
        type=nonnegative,
        default=0,
        help=(
            "Optional initial offset half-width. "
            "Excluded by default; avoid double counting."
        )
    )

    argument_parser.add_argument(
        "--convention",
        choices=["limits-rss", "rectangular-standard"],
        default="limits-rss"
    )

    argument_parser.add_argument(
        "--sig-figs",
        choices=[1, 2],
        type=int,
        default=2
    )

    return argument_parser


def save_csv(path, rows):
    with path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file, fieldnames=list(rows[0])
        )
        writer.writeheader()
        writer.writerows(rows)


def save_plot(figure, folder, name):
    for extension in ("png", "pdf", "svg"):
        figure.savefig(
            folder / f"{name}.{extension}",
            dpi=300,
            bbox_inches="tight",
            facecolor="white"
        )

    plt.close(figure)


def main(argv=None):
    args = parser().parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    # Identify missing instrument inputs.
    unknown = []

    if args.supply_limit_v is None:
        unknown.append("supply uncertainty")

    if (
        args.meter_percent is None
        or args.meter_absolute_v is None
    ):
        unknown.append("meter uncertainty")

    provisional = bool(unknown)

    if args.convention == "rectangular-standard":
        scale = math.sqrt(3)
    else:
        scale = 1.0

    # Missing inputs contribute zero only to this partial budget.
    # They are not represented as established zero uncertainties.
    reference_limit = REFERENCE_KOHM * TOLERANCE
    supply_limit = args.supply_limit_v or 0.0

    meter_limit = (
        np.abs(DELTA_V)
        * (args.meter_percent or 0)
        / 100
        + (args.meter_absolute_v or 0)
    )

    voltage_input = np.hypot(
        meter_limit,
        args.balance_limit_v
    ) / scale

    calculated = resistance(
        REFERENCE_KOHM, SUPPLY_V, DELTA_V
    )

    derivative_r, derivative_s, derivative_d = sensitivities(
        REFERENCE_KOHM, SUPPLY_V, DELTA_V
    )

    components = np.column_stack([
        np.abs(derivative_r) * reference_limit / scale,
        np.abs(derivative_s) * supply_limit / scale,
        np.abs(derivative_d) * voltage_input
    ])

    propagated = np.linalg.norm(
        components, axis=1
    )

    # The reference and supply are shared inputs.
    # Their contributions therefore correlate the resistance estimates.
    # Meter contributions are assumed independent across readings.
    covariance = (
        np.outer(derivative_r, derivative_r)
        * (reference_limit / scale)**2
        + np.outer(derivative_s, derivative_s)
        * (supply_limit / scale)**2
    )

    covariance += np.diag(
        (derivative_d * meter_limit / scale)**2
    )

    covariance += (
        np.outer(derivative_d, derivative_d)
        * (args.balance_limit_v / scale)**2
    )

    signed_error = (
        100
        * (calculated - NOMINAL_KOHM)
        / NOMINAL_KOHM
    )

    if provisional and not np.any(components[:, 1:]):
        label = "PARTIAL: reference contribution only"
    elif provisional:
        label = "PARTIAL: unconfirmed inputs omitted"
    else:
        label = "Specified-input propagation"

    if scale == 1:
        convention_label = (
            "RSS of input limits; no confidence level"
        )
    else:
        convention_label = (
            "Combined standard uncertainty; k = 1"
        )

    # Build formatted and full-precision result tables.
    formatted_rows = []
    full_rows = []

    for index, values in enumerate(zip(
        NOMINAL_KOHM,
        DELTA_V,
        calculated,
        propagated,
        signed_error
    )):
        nominal, voltage, result, contribution, error = values

        _, _, nominal_text = reported(
            nominal,
            nominal * TOLERANCE,
            args.sig_figs
        )

        result_text, contribution_text, pair = reported(
            result,
            contribution,
            args.sig_figs
        )

        formatted_rows.append({
            "Nominal ± 1% (kohm)": nominal_text,
            "Measured dV (V)": f"{voltage:g}",
            "Calculated resistance ± contribution (kohm)": pair,
            "Absolute error (%)": f"{abs(error):.2f}",
            "Budget status": label
        })

        full_rows.append({
            "nominal_kohm": nominal,
            "nominal_tolerance_limit_kohm": nominal * TOLERANCE,
            "delta_v": voltage,
            "calculated_kohm": result,
            "propagated_contribution_kohm": contribution,
            "reported_value_kohm": result_text,
            "reported_contribution_kohm": contribution_text,
            "signed_error_percent": error,
            "absolute_error_percent": abs(error),
            "sensitivity_to_R": derivative_r[index],
            "sensitivity_to_Vs_kohm_per_V": derivative_s[index],
            "sensitivity_to_dV_kohm_per_V": derivative_d[index],
            "reference_contribution_kohm": components[index, 0],
            "supply_contribution_kohm": components[index, 1],
            "voltage_contribution_kohm": components[index, 2]
        })

    save_csv(
        args.out / "resistance_table_formatted.csv",
        formatted_rows
    )

    save_csv(
        args.out / "resistance_table_full_precision.csv",
        full_rows
    )

    np.savetxt(
        args.out / "resistance_covariance_kohm2.csv",
        covariance,
        delimiter=",",
        header=(
            "Order: nominal resistances "
            "4,6,8,10,12,14,16,18,20 kohm. "
            "Correlations depend on model assumptions."
        )
    )

    settings = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    }

    metadata = {
        "source": SOURCE_DESCRIPTION,
        "supply_v": SUPPLY_V,
        "reference_kohm": REFERENCE_KOHM,
        "resistor_tolerance_fraction": TOLERANCE,
        "uncertainty_convention": args.convention,
        "unknown_inputs": unknown,
        "provisional": provisional,
        "budget_status": label,
        "settings": settings,
        "assumptions": [
            "Right midpoint = Vs/2; negligible meter loading.",
            "Nominal resistor values used for percent error.",
            "All results share the uncertain reference resistor.",
            (
                "Default budget omits supply, meter, initial "
                "balance offset, and divider-ratio uncertainty."
            ),
            (
                "Instrument input flags alone do not validate "
                "the idealized bridge model."
            ),
            (
                "No confidence or coverage probability is "
                "attached to RSS of limits."
            )
        ]
    }

    (args.out / "analysis_settings.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8"
    )

    markdown = [
        "# Resistance analysis",
        "",
        f"**{label}.** {convention_label}.",
        "",
        (
            "The ± entries are partial contributions until "
            "the missing inputs are supplied."
        ),
        "",
        (
            "| Nominal ± 1% (kΩ) | δV (V) | "
            "Calculated ± contribution (kΩ) | "
            "Absolute error (%) |"
        ),
        "|---:|---:|---:|---:|"
    ]

    for row in formatted_rows:
        values = list(row.values())[:4]
        markdown.append(
            "| " + " | ".join(values) + " |"
        )

    markdown.extend([
        "",
        (
            "Calculations retained full precision; displayed "
            "resistance and uncertainty share a decimal position."
        ),
        (
            "The suspect component is excluded because "
            "its voltage sign is unconfirmed."
        ),
        f"Source: {SOURCE_DESCRIPTION}"
    ])

    (args.out / "resistance_table.md").write_text(
        "\n".join(markdown) + "\n",
        encoding="utf-8"
    )

    # Plot appearance
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "axes.edgecolor": "#4B5563",
        "axes.linewidth": 0.8,
        "grid.alpha": 0.22,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.dpi": 300
    })

    # Figure 1: resistance comparison and signed error
    figure, (axis, residual_axis) = plt.subplots(
        2, 1,
        figsize=(7.4, 7.2),
        sharex=True,
        gridspec_kw={"height_ratios": [1.4, 1]},
        layout="constrained"
    )

    fine = np.linspace(3, 21, 300)

    axis.fill_between(
        fine,
        0.99 * fine,
        1.01 * fine,
        color=GRAY,
        alpha=0.15,
        label="Nominal ±1% tolerance"
    )

    axis.plot(
        fine, fine,
        "--",
        color=GRAY,
        linewidth=1,
        label="Ideal agreement"
    )

    axis.errorbar(
        NOMINAL_KOHM,
        calculated,
        yerr=propagated,
        fmt="o",
        color=BLUE,
        capsize=4,
        markersize=5,
        label="Bridge result ± propagated contribution"
    )

    axis.set(
        ylabel="Calculated resistance (kΩ)",
        title="Resistance measurements and agreement with nominal values",
        xlim=(3, 21)
    )

    axis.grid(True)
    axis.legend(loc="upper left", fontsize=8)

    residual_axis.axhspan(
        -1, 1,
        color=GRAY,
        alpha=0.12,
        label="±1% nominal tolerance scale"
    )

    residual_axis.axhline(
        0, color=GRAY, linewidth=1
    )

    residual_axis.errorbar(
        NOMINAL_KOHM,
        signed_error,
        yerr=100 * propagated / NOMINAL_KOHM,
        fmt="o",
        color=BLUE,
        capsize=4,
        markersize=5
    )

    residual_axis.set(
        xlabel="Nominal resistance (kΩ)",
        ylabel="Signed difference (%)",
        xticks=NOMINAL_KOHM
    )

    residual_axis.grid(True)
    residual_axis.legend(
        loc="lower right", fontsize=8
    )

    figure.suptitle(
        f"{label}\n{convention_label}",
        fontsize=10,
        color=ORANGE
    )

    save_plot(
        figure,
        args.out,
        "01_resistance_comparison"
    )

    # Figure 2: bridge response and voltage residuals
    figure, (axis, residual_axis) = plt.subplots(
        2, 1,
        figsize=(7.4, 6.6),
        sharex=True,
        gridspec_kw={"height_ratios": [1.7, 1]},
        layout="constrained"
    )

    grid = np.linspace(3.5, 20.5, 400)

    model = (
        SUPPLY_V * REFERENCE_KOHM
        / (grid + REFERENCE_KOHM)
        - SUPPLY_V / 2
    )

    predicted = (
        SUPPLY_V * REFERENCE_KOHM
        / (NOMINAL_KOHM + REFERENCE_KOHM)
        - SUPPLY_V / 2
    )

    axis.plot(
        grid,
        model,
        color=GRAY,
        linewidth=1.5,
        label="Ideal bridge model"
    )

    axis.scatter(
        NOMINAL_KOHM,
        DELTA_V,
        color=BLUE,
        s=35,
        zorder=3,
        label="Recorded voltage"
    )

    axis.axhline(
        0, color=GRAY, linewidth=0.7
    )

    axis.set(
        ylabel="Differential voltage (V)",
        title="Bridge response to the substituted resistance"
    )

    axis.grid(True)
    axis.legend(fontsize=9)

    residual_axis.axhline(
        0, color=GRAY, linewidth=1
    )

    residual_axis.scatter(
        NOMINAL_KOHM,
        1000 * (DELTA_V - predicted),
        color=BLUE,
        s=35
    )

    residual_axis.set(
        xlabel="Nominal resistance (kΩ)",
        ylabel="Measured − ideal (mV)",
        xticks=NOMINAL_KOHM
    )

    residual_axis.grid(True)

    figure.suptitle(
        "Ideal curve uses nominal values; instrument uncertainty not shown",
        fontsize=10,
        color=ORANGE
    )

    save_plot(
        figure,
        args.out,
        "02_bridge_response"
    )

    # Figure 3: suspect resistor sign scenarios and replacement
    # Both signs are retained as scenarios.
    suspect_voltages = np.array([1.28, -1.28])

    suspect_resistances = resistance(
        REFERENCE_KOHM,
        SUPPLY_V,
        suspect_voltages
    )

    suspect_rows = [
        {
            "scenario": f"{voltage:+.2f} V original reading",
            "voltage_v": voltage,
            "inferred_kohm": result,
            "absolute_error_percent": 100 * abs(result - 10) / 10,
            "status": "SIGN UNCONFIRMED; excluded from main table"
        }
        for voltage, result in zip(
            suspect_voltages, suspect_resistances
        )
    ]

    save_csv(
        args.out / "suspect_resistor_scenarios.csv",
        suspect_rows
    )

    figure, axis = plt.subplots(
        figsize=(7.4, 3.9),
        layout="constrained"
    )

    labels = [
        "Original if +1.28 V",
        "Original if −1.28 V",
        "Replacement +0.45 V"
    ]

    values = np.r_[
        suspect_resistances, calculated[3]
    ]
    positions = np.arange(3)

    axis.axvspan(
        9.9, 10.1,
        color=GRAY,
        alpha=0.18,
        label="10 kΩ nominal ±1%"
    )

    axis.scatter(
        values[:2],
        positions[:2],
        color=ORANGE,
        marker="x",
        s=65,
        linewidths=2,
        label="Unconfirmed sign scenarios"
    )

    axis.scatter(
        values[2],
        positions[2],
        color=BLUE,
        marker="o",
        s=45,
        label="Replacement"
    )

    for result, position in zip(values, positions):
        axis.annotate(
            f"{result:.3f} kΩ",
            (result, position),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=9
        )

    axis.set(
        yticks=positions,
        yticklabels=labels,
        xlabel="Resistance inferred from bridge voltage (kΩ)",
        title="Suspect 10 kΩ component and replacement",
        xlim=(5.5, 23),
        ylim=(-0.55, 3.0)
    )

    axis.invert_yaxis()
    axis.grid(axis="x")
    axis.legend(
        loc="lower right", fontsize=8
    )

    save_plot(
        figure,
        args.out,
        "03_suspect_resistor"
    )

    # Console output
    print(label + " | " + convention_label)

    print(
        "Nominal kΩ | Measured V | "
        "Calculated kΩ ± contribution | Absolute error"
    )

    for row in formatted_rows:
        print(" | ".join(list(row.values())[:4]))

    print(
        "\nSaved tables, settings, covariance, and "
        f"PNG/PDF/SVG plots to {args.out.resolve()}"
    )

    if unknown:
        print(
            "Still needed: "
            + ", ".join(unknown)
            + ". These omitted inputs are not known to be zero."
        )

    return calculated, propagated


if __name__ == "__main__":
    main()
