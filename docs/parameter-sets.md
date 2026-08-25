# Parameter Sets and Matrices

The CLI and Python clients share the same declarations and resolver.
`COMMON_PARAMS`, `PARAM_SETS`, and `PARAM_MATRIX` contain literal values; paths
to external parameter files are not a parameter mechanism because those files
would escape `REQUIRES`.

## Declarations

```python
COMMON_PARAMS = {"simulator": "ngspice"}

PARAM_SETS = [
    {
        "name": "tt_1v80_27c",
        "description": "typical process at 1.80 V and 27 C",
        "params": {"process": "tt", "vdd_v": 1.80, "temp_c": 27},
    },
    {
        "name": "ss_1v62_125c",
        "targetdir": "custom_slow_run",
        "params": {"process": "ss", "vdd_v": 1.62, "temp_c": 125},
    },
]

PARAM_MATRIX = {
    "load_pf": [0.5, 1.0],
}
```

Set names are unique Python identifiers. Common parameters merge beneath each
set. Matrix axes are explicit non-empty lists, expanded in declaration order,
and matrix values win over set/common values with the same key.

Use `variants(read(path))` to obtain the fully expanded values as data without
building edits or rendering. Use `variants(declarations)` when caller-owned
definitions must be known while composing a Plan; that path reads no edit file.

## Three embedding modes and identity

An embedded `resolve` call produces one variant. Its three caller modes are:

| Caller passes | In identity via | Invalidation when a corner changes |
| --- | --- | --- |
| explicit params | declared config | only the affected point |
| a selector | config name plus edit-file fingerprint | every point declaring the file — coarse |
| supplied definitions | declared config only | only the affected point |

### Explicit parameters

```python
plan = resolve(
    edit_path,
    requires={"base": base_path},
    params={"process": "ss", "vdd_v": 1.62, "temp_c": 125},
)
```

The point values must be declared operation config. They override
`COMMON_PARAMS` and do not consult named sets or the matrix. This deliberately
restates point values when fine-grained reuse matters.

### Selector

```python
plan = resolve(
    edit_path,
    requires={"base": base_path},
    selector="ss_1v62_125c",
)
```

The caller declares only the name; values remain authored once in the edit file
and are covered by that file's fingerprint. This is simplest, but any edit to
the file invalidates every invocation that declares it. A selector combined
with a non-empty matrix is ambiguous for a single embedded invocation and is
rejected; expand first and pass one expanded point as explicit params.

### Supplied definitions, then selection

```python
caller_declarations = {
    "PARAM_SETS": [
        {"name": "ss", "params": {"process": "ss", "vdd_v": 1.62}},
    ],
}

plan = resolve(
    edit_path,
    declarations=caller_declarations,
    requires={"base": base_path},
    selector="ss",
)
```

`declarations` is one uniform channel keyed by the same uppercase names as an
edit file. A supplied value replaces the file's whole declaration; it is not
merged. That applies equally to `REQUIRES`, `COMMON_PARAMS`, `PARAM_SETS`, and
`PARAM_MATRIX`. Selection is separate, so supplying a set definition and then
naming one reads naturally.

The complete supplied definition **must be declared operation config**. For the
fine-grained behavior in the identity table, each invocation receives a
one-item replacement list containing only its own complete set definition. If
every invocation instead receives the full collection, changing one entry
necessarily changes every invocation's config and invalidates them all.

If a study passes a module constant or local mapping outside declared config,
edits to that mapping are invisible to reuse and cached attempts remain falsely
valid. The API cannot infer a value's Hedloom origin, so this is a caller
contract, not an optimization hint.

## CLI expansion and output layout

```bash
sidecar-render edits.py /tmp/run
sidecar-render edits.py /tmp/run --run tt_1v80_27c
sidecar-render edits.py /tmp/run --run tt_1v80_27c --run ss_1v62_125c
sidecar-render edits.py /tmp/run --all
```

The CLI loops over all named sets by default; `--run` selects sets before matrix
expansion. With no named sets, the output argument is the run directory. Named
sets render beside it as `<output>_<set>`, unless `targetdir` replaces that
parent. Matrix cases render one level below using stable slugs such as
`temp_c_m40` and `vdd_1p20`.

Existing output directories are refused. `COPY_IGNORE` patterns exclude stale
files while copying the base. A trailing `/` matches directories, a pattern
containing `/` matches the base-relative path, and other patterns match names.

## Plan-time rule

A study must not read an edit file while composing its Plan. Values read then
are frozen into Plan declarations, while the later render may receive different
caller declarations or requirement bindings; nothing compares the two.

If a value genuinely must be known at plan time, obtain it through the same
resolver and with the same inputs the render uses. Prefer caller-owned
declarations with `variants(declarations)`, which performs no file I/O. Reading
the edit file through `read` at plan time is the exceptional fallback and gives
up the no-file-I/O property.
