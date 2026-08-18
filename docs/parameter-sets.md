# Parameter Sets and Matrices

Parameters are defined inside the edit file, not assembled on the command line.
One edit file describes the study; the CLI only selects which of its runs to
prepare.

## Common Parameters

For a single run, inline common parameters are enough:

```python
COMMON_PARAMS = {
    "netlist_path": "/work/netlists/rc_filter_corner_tt.scs",
    "vdd": "1.2",
}
```

`COMMON_PARAMS_FILE` loads the same mapping from a JSON file next to the edit
file instead. Defining both is an error.

## Named Parameter Sets

`PARAM_SETS` turns one edit file into several named runs. A set has a required
identifier `name`, an optional `description`, an optional `targetdir`, and
either inline `params` or a `params_file` pointing at JSON. `COMMON_PARAMS` are
merged into every set, and set-specific values win.

```python
COMMON_PARAMS = {
    "simulator_cmd": "spectre",
}

PARAM_SETS = [
    {
        "name": "tt_1v2",
        "description": "typical corner at 1.2 V",
        "params_file": "params.json",
    },
    {
        "name": "ss_0v9",
        "targetdir": "custom_ss_run",
        "params": {
            "netlist_path": "/work/netlists/rc_filter_ss.scs",
            "vdd": "0.90",
        },
    },
]
```

Names must be valid Python identifiers and must not repeat. A set that defines
both `params` and `params_file` is an error.

## Parameter Matrix

`PARAM_MATRIX` renders every combination of a few explicit axes. It is applied
after parameter-set selection, so matrix values override common and
set-specific values for the same key, and each combination is rendered one
level deeper.

```python
PARAM_MATRIX = {
    "vdd": ["0.90", "1.20"],
    "temp_c": [27, 125],
}
```

The matrix syntax intentionally accepts explicit lists only. Generate the list
in Python if you want sweep syntax; the edit file is already a Python program.

## Selecting Runs

```bash
sidecar-render examples/basic/edits.py /tmp/run
sidecar-render examples/basic/edits.py /tmp/run --run tt_1v2
sidecar-render examples/basic/edits.py /tmp/run --run tt_1v2 --run ss_0v9
sidecar-render examples/basic/edits.py /tmp/run --all
```

Rendering every named set is the default. `--run` selects one or more sets
before matrix expansion, and `--all` is accepted mostly for readability. Using
both at once is an error, as is naming a set the edit file does not define — the
error lists the names that are available.

## Output Layout

Without `PARAM_SETS`, the output argument is the run directory. With named sets
it is a base path, and each set is written beside it as `<output>_<name>` unless
the set gives a `targetdir`. A relative `targetdir` is resolved against the
output path's parent; an absolute one is used as given. Matrix cases are then
rendered one level below that.

For `sidecar-render edits.py /tmp/run` with the sets and matrix above:

```text
/tmp/run_tt_1v2/vdd_0p90_temp_c_27/
/tmp/run_tt_1v2/vdd_0p90_temp_c_125/
/tmp/run_tt_1v2/vdd_1p20_temp_c_27/
/tmp/run_tt_1v2/vdd_1p20_temp_c_125/
/tmp/custom_ss_run/vdd_0p90_temp_c_27/
/tmp/custom_ss_run/vdd_0p90_temp_c_125/
```

Matrix directory names are slugs of the key and value: `.` becomes `p`, a
leading `-` becomes `m`, and any other run of non-identifier characters becomes
`_`. So `temp_c = -40` renders under `temp_c_m40`.

Rendering refuses to write into a directory that already exists. Remove the old
run, or render somewhere else, rather than editing a rendered tree in place —
the base directory stays authoritative.

## Excluding Files From The Copy

`COPY_IGNORE` drops paths while the base tree is copied, before any edit runs.
It is useful for stale simulator output and scratch files that should not be
inherited by a new run.

```python
COPY_IGNORE = [
    "psf/",
    "*.tmp",
]
```

A pattern ending in `/` matches directories only. A pattern containing `/` is
matched against the path relative to the base directory; otherwise it is matched
against the file name alone. Blank lines and lines beginning with `#` are
ignored.

## Environment Variables In Paths

Path-like fields expand environment variables such as `$PDK_ROOT` and
`${RUN_ROOT}` after parameter formatting. This applies to `BASE_DIR`,
`COMMON_PARAMS_FILE`, per-set `params_file`, the CLI output path, `targetdir`,
edit target paths, `copy_file` source and destination paths, `extract_subckts`
file fields, and command arguments. Replacement text is left alone, so
simulator-side environment variables survive into the rendered netlist.
