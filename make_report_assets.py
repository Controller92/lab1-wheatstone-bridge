from pathlib import Path
import os
import tempfile

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "lab-report-mpl")
)

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


output = Path(__file__).parent / "report-assets"
output.mkdir(exist_ok=True)

nominal = np.arange(4, 22, 2, dtype=float)

voltage = np.array([
    2.511, 1.648, 1.01, 0.45, 0.002,
    -0.39, -0.72, -1.01, -1.27
])

calculated = 12 * (10 - 2 * voltage) / (10 + 2 * voltage)

# Preliminary reference-resistor contribution only.
contribution = 0.01 * calculated
error = 100 * (calculated - nominal) / nominal

blue = "#215A8A"
gray = "#626A73"
orange = "#B76B28"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "grid.alpha": 0.18,
    "legend.frameon": False
})


def save(figure, name):
    figure.savefig(
        output / name,
        dpi=300,
        bbox_inches="tight",
        facecolor="white"
    )
    plt.close(figure)


# Resistance comparison
figure, (axis, residual_axis) = plt.subplots(
    1, 2,
    figsize=(8, 3.1),
    layout="constrained"
)

grid = np.linspace(3, 21, 200)

axis.fill_between(
    grid,
    0.99 * grid,
    1.01 * grid,
    color=gray,
    alpha=0.15,
    label="Nominal ±1%"
)

axis.plot(
    grid, grid,
    "--",
    linewidth=1,
    color=gray,
    label="Ideal agreement"
)

axis.errorbar(
    nominal,
    calculated,
    yerr=contribution,
    fmt="o",
    markersize=4,
    color=blue,
    capsize=3,
    label="Bridge result"
)

axis.set(
    xlabel="Nominal resistance (kΩ)",
    ylabel="Calculated resistance (kΩ)",
    xticks=[4, 8, 12, 16, 20]
)

axis.legend(fontsize=8)
axis.grid(True)

residual_axis.axhspan(
    -1, 1,
    color=gray,
    alpha=0.13,
    label="±1% nominal scale"
)

residual_axis.axhline(
    0, color=gray, linewidth=0.8
)

residual_axis.errorbar(
    nominal,
    error,
    yerr=100 * contribution / nominal,
    fmt="o",
    markersize=4,
    color=blue,
    capsize=3
)

residual_axis.set(
    xlabel="Nominal resistance (kΩ)",
    ylabel="Signed difference (%)",
    xticks=[4, 8, 12, 16, 20]
)

residual_axis.grid(True)
residual_axis.legend(
    fontsize=8, loc="lower right"
)

save(figure, "comparison.png")


# Bridge voltage response
figure, (axis, residual_axis) = plt.subplots(
    1, 2,
    figsize=(8, 3.0),
    layout="constrained"
)

grid = np.linspace(3.5, 20.5, 400)
model = 120 / (grid + 12) - 5
predicted = 120 / (nominal + 12) - 5

axis.plot(
    grid,
    model,
    color=gray,
    linewidth=1.4,
    label="Ideal bridge"
)

axis.scatter(
    nominal,
    voltage,
    color=blue,
    s=25,
    label="Measured"
)

axis.set(
    xlabel="Nominal resistance (kΩ)",
    ylabel="Differential voltage (V)",
    xticks=[4, 8, 12, 16, 20]
)

axis.grid(True)
axis.legend(fontsize=8)

residual_axis.axhline(
    0, color=gray, linewidth=0.8
)

residual_axis.scatter(
    nominal,
    1000 * (voltage - predicted),
    color=blue,
    s=25
)

residual_axis.set(
    xlabel="Nominal resistance (kΩ)",
    ylabel="Measured − ideal (mV)",
    xticks=[4, 8, 12, 16, 20]
)

residual_axis.grid(True)

save(figure, "voltage.png")


# Suspect component
figure, axis = plt.subplots(
    figsize=(8, 2.6),
    layout="constrained"
)

values = [
    12 * (10 - 2 * 1.28) / (10 + 2 * 1.28),
    12 * (10 + 2 * 1.28) / (10 - 2 * 1.28),
    calculated[3]
]

axis.axvspan(
    9.9, 10.1,
    color=gray,
    alpha=0.18,
    label="10 kΩ nominal ±1%"
)

axis.scatter(
    values[:2],
    [0, 1],
    marker="x",
    s=50,
    color=orange,
    label="Unconfirmed sign scenarios"
)

axis.scatter(
    values[2],
    2,
    color=blue,
    s=30,
    label="Replacement"
)

for result, position in zip(values, range(3)):
    axis.annotate(
        f"{result:.3f} kΩ",
        (result, position),
        xytext=(6, 8),
        textcoords="offset points",
        fontsize=9
    )

axis.set(
    xlabel="Inferred resistance (kΩ)",
    yticks=[0, 1, 2],
    yticklabels=[
        "Original if +1.28 V",
        "Original if −1.28 V",
        "Replacement +0.45 V"
    ],
    xlim=(5.5, 23),
    ylim=(-0.6, 3.0)
)

axis.invert_yaxis()
axis.grid(axis="x")
axis.legend(loc="lower right", fontsize=8)

save(figure, "suspect.png")


# Conceptual circuit used for the idealized model.
# This does not specify the potentiometer's physical bridge arm.
figure, axis = plt.subplots(figsize=(8, 1.8))

axis.set(
    xlim=(-1.6, 5),
    ylim=(-0.3, 3.6)
)
axis.axis("off")


def wire(x_values, y_values):
    axis.plot(
        x_values,
        y_values,
        color="#333333",
        linewidth=1.3
    )


def resistor(x_position, y_position, label):
    y_values = np.linspace(
        y_position - 0.4,
        y_position + 0.4,
        9
    )

    x_values = x_position + np.array([
        0, 0.11, -0.11, 0.11, -0.11,
        0.11, -0.11, 0.11, 0
    ])

    wire(x_values, y_values)

    axis.text(
        x_position + 0.25,
        y_position,
        label,
        va="center",
        fontsize=11
    )


for x_position in [0, 3]:
    wire(
        [x_position, x_position],
        [3, 2.7]
    )

    resistor(
        x_position,
        2.3,
        r"$R_x$" if x_position == 0 else r"$R_3$"
    )

    wire(
        [x_position, x_position],
        [1.9, 1.1]
    )

    resistor(
        x_position,
        0.7,
        r"$R$" if x_position == 0 else r"$R_4$"
    )

    wire(
        [x_position, x_position],
        [0.3, 0]
    )

wire([0, 3], [3, 3])
wire([0, 3], [0, 0])

wire([0, 0.9], [1.5, 1.5])
wire([2.1, 3], [1.5, 1.5])

axis.add_patch(
    plt.Circle(
        (1.5, 1.5),
        0.40,
        fill=False,
        color="#333333",
        linewidth=1.2
    )
)

axis.text(
    1.5, 1.5, "V",
    ha="center", va="center"
)

axis.text(0.8, 1.8, "+", fontsize=12)
axis.text(2.05, 1.8, "−", fontsize=12)

axis.text(
    1.5, 0.8,
    r"$\delta V=V_L-V_R$",
    ha="center",
    fontsize=11
)

axis.text(
    -0.3, 3.05,
    r"$V_s$",
    ha="right"
)

axis.text(
    -0.3, 0,
    "0 V",
    ha="right"
)

axis.text(
    3.5, 3.1,
    "Balanced reference branch",
    fontsize=10,
    ha="center"
)

axis.text(
    3.5, -0.25,
    r"$V_R=V_s/2$ in ideal model",
    fontsize=10,
    ha="center"
)

for x_position in [0, 3]:
    axis.scatter(
        [x_position, x_position, x_position],
        [0, 1.5, 3],
        color="#333333",
        s=10,
        zorder=3
    )

save(figure, "schematic.png")


# Reproduce the cropped notebook illustration.
# Use a scan beside this script, or the original parent-directory location.
# The scan is optional and is not needed for the analysis figures.
notebook_path = Path(__file__).resolve().parent / "notebook.png"
if not notebook_path.is_file():
    notebook_path = Path(__file__).resolve().parents[1] / "notebook.png"

if notebook_path.is_file():
    with Image.open(notebook_path) as image:
        image.crop((
            0,
            0,
            image.width,
            int(image.height * 0.70)
        )).save(output / "notebook_crop.png")
else:
    print("Optional notebook.png not supplied; skipping notebook crop.")

print(output)
