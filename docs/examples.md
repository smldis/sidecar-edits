# Examples

This unit includes small runnable examples under `examples/`. Run them from the
unit root, `sidecar-edits/`, after installing the package:

```bash
python -m pip install -e .
```

## Basic Edits

```bash
sidecar-render examples/basic/edits.py /tmp/sidecar_example_run
```

This copies a base simulator input directory, extracts subcircuits, copies an
asset, and replaces one include path.

## Apply Patch

```bash
sidecar-render examples/apply_patch/edits.py /tmp/sidecar_apply_patch_run
```

This exercises `extract_subckts`, `copy_file`, literal replacement, regex
replacement, system `patch`, and `apply_patch`. It also uses `COPY_IGNORE` to
leave stale `psf/` output and `*.tmp` scratch files behind in the base tree, and
loads its parameters from `params.json`. Because it defines one named parameter
set, it renders `/tmp/sidecar_apply_patch_run_tt_1v2`.

## Parameter Matrix

```bash
sidecar-render examples/param_matrix/edits.py /tmp/sidecar_matrix_run
```

This renders two named process corners against an explicit voltage and
temperature matrix — six run directories per corner, with the slow corner
redirected by `targetdir` to `/tmp/custom_ss_sweep`. See
[Parameter Sets and Matrices](parameter-sets.md) for the rules it follows.

## Excel PWL Sources

```bash
sidecar-render examples/pwl_excel/edits.py /tmp/sidecar_pwl_excel_run
```

This reads `examples/pwl_excel/waveforms/startup.xlsx`, converts the sheet named
`startup` into named `PWL(...)` expressions, writes
`generated/pwl_sources.inc`, and appends an include statement to `input.scs`.

The workbook follows the table convention used by `sidecar_edits.pwl`:

| #time | vin | vclk | ireset |
| --- | --- | --- | --- |
| 0 | 0 | 0 | |
| 1n | 0.2 | 1.2 | |
| 2n | | 0 | 1m |
| 5n | 1.2 | | 0 |

The first column must be `#time`. Each remaining column is a source name. Blank
cells mean "do not emit a point for this source at this time."

```{literalinclude} ../examples/pwl_excel/edits.py
:language: python
```
