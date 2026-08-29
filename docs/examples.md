# Examples

Install the package from the unit root before running the examples:

```bash
python -m pip install -e .
```

Every command starts from a clean output path.

## Basic edits

```bash
sidecar-render examples/basic/edits.py /tmp/sidecar_basic
```

The authoring file declares `base` and `model_override`, extracts subcircuits,
copies the declared model asset, and substitutes the authored include path.

## Patch transformations

```bash
sidecar-render examples/apply_patch/edits.py /tmp/sidecar_patch
```

This exercises extraction, copy, literal and regex replacement, system `patch`,
and `apply_patch`. Its one named set renders to `/tmp/sidecar_patch_tt_1v2`.
`COPY_IGNORE` excludes stale simulator output and scratch files. The point's
parameters are literal in the set definition; no undeclared JSON file is read.

## Parameter matrix

```bash
sidecar-render examples/param_matrix/edits.py /tmp/sidecar_matrix
sidecar-render examples/param_matrix/edits.py /tmp/sidecar_matrix_tt --run tt
```

The first command renders two process sets across six voltage/temperature
matrix cases each. The second selects the typical set before expansion.

## Excel-backed PWL sources

```bash
sidecar-render examples/pwl_excel/edits.py /tmp/sidecar_pwl
```

The file declares `startup_table` with default
`waveforms/startup.xlsx`. Its `edits_for(ctx)` reads
`ctx.requires["startup_table"]`, converts the `startup` sheet to PWL source
lines, and returns write/append edits. Importing or calling `read` on the module
does not open the workbook. Text payloads are now verbatim by default. These
generated write/append payloads need no parameter interpolation; authored
templates opt in with `interpolate=True`, and arguments that need environment
expansion opt in with `expand_env=True`. The user guide shows the corresponding
declared-netlist pattern and the rule shared by all formatted edit arguments.

```{literalinclude} ../examples/pwl_excel/edits.py
:language: python
```

The table convention is:

| #time | vin | vclk | ireset |
| --- | --- | --- | --- |
| 0 | 0 | 0 | |
| 1n | 0.2 | 1.2 | |
| 2n | | 0 | 1m |
| 5n | 1.2 | | 0 |

Blank cells omit points; they do not mean zero.
