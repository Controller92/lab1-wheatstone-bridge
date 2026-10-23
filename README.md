# Lab 1: Wheatstone Bridge Analysis

Python code used to analyze recorded Wheatstone bridge measurements and generate lab-report figures. The nine nominal resistance values and measured differential voltages are embedded in both scripts. These scripts analyze recorded data; they do not acquire live measurements from a DAQ device.

## Files

- [`analyze_lab1.py`](analyze_lab1.py): calculates resistance, signed and absolute percentage differences, sensitivity coefficients, propagated contributions, covariance, and suspect-resistor sign scenarios. Writes tables, metadata, and plots.
- [`make_report_assets.py`](make_report_assets.py): generates compact report figures and an idealized bridge schematic; optionally crops a supplied notebook image.
- [`requirements.txt`](requirements.txt): Python dependencies.

## Run

Use Python 3.10 or newer. No MATLAB or NI driver is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python analyze_lab1.py
python make_report_assets.py
```

On Windows, use `py -m venv .venv` to create the environment and `.venv\Scripts\activate` to activate it, then run the same `python` commands.

`analyze_lab1.py` saves files in `results/` by default:

- Formatted and full-precision resistance tables (CSV), and a Markdown table.
- Resistance covariance matrix (CSV).
- Analysis settings and assumptions (JSON).
- Suspect-resistor scenarios (CSV).
- Three figures, each in PNG, PDF, and SVG formats.

To choose another output directory or view the available uncertainty inputs:

```bash
python analyze_lab1.py --out results/custom
python analyze_lab1.py --help
```

`make_report_assets.py` saves `comparison.png`, `voltage.png`, `suspect.png`, and `schematic.png` in `report-assets/`. To generate the optional notebook crop, place your own `notebook.png` beside the script. The original location one directory above the script is also supported. No notebook scan is included in this repository.

## Model and uncertainty interpretation

The idealized model assumes a right-hand midpoint of half the supply voltage, negligible meter loading, a 12 kΩ reference resistor, and a 10 V supply. With differential voltage defined as left midpoint minus right midpoint:

```text
Rx = Rref × (Vs − 2ΔV) / (Vs + 2ΔV)
```

Resistances are expressed in kΩ and voltages in V. Nominal resistance labels are not independent resistance measurements.

**Default uncertainty results are provisional.** The analysis includes the 1% reference-resistor contribution, while supply and meter uncertainty inputs remain unknown. Omitted contributions are not established zero uncertainties. The default root-sum-square of limits is an engineering estimate with no assigned confidence level. The report-assets script also shows only the preliminary reference-resistor contribution.

Use `--supply-limit-v`, `--meter-percent`, and `--meter-absolute-v` only with justified instrument specifications. The optional `--convention rectangular-standard` divides independent rectangular input limits by √3 to produce standard-uncertainty contributions. Specifying these inputs does not validate the idealized bridge model or include every possible systematic effect.

The suspect resistor's original voltage sign is unconfirmed. Both sign scenarios are shown and excluded from the main resistance table.

## Reproduction notes

The supplied calculations and measurements are preserved. Packaging changes make the report-assets cache path portable and allow its figures to finish without the optional notebook scan. A private ChatGPT Library file reference from the supplied script has been replaced with a description of the embedded measurements; no external file is downloaded or needed to run either script.

Generated results and personal notebook scans are ignored by Git. Regenerate the results using the commands above.
