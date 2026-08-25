# Sidecar Edits

Sidecar Edits is the simulation-directory preparation unit of
[Analog Sim Studies](../README.md). Its contract and exclusions are recorded in
[ONTOLOME.md](ONTOLOME.md); the parent vision remains in
[`../MANIFESTO.md`](../MANIFESTO.md).

## Breaking 0.2 release

Version 0.2 is an intentional breaking authoring and embedding API change with
no deprecation period. Edit files now define exactly `edits_for(ctx)` and name
external inputs in `REQUIRES`. Python clients use the published
`sidecar_edits.render` contract. Arbitrary command edits and JSON parameter-file
locators were removed: simulator execution belongs to the caller, and every
external input must be named and handed to the edit file.

## Layout

- `src/sidecar_edits/` contains the preparation package.
- `examples/` contains four runnable authoring files.
- `tests/` contains unit and end-to-end coverage.
- `docs/` is the maintained published guide.
- `design/` is a dated, unpublished design record.

## Install and run

Sidecar Edits requires Python 3.10 or newer and a C compiler for the packaged
subcircuit helper. The patch examples additionally need `patch` and
`apply_patch` on `PATH`.

```bash
python -m pip install -e .
sidecar-render examples/basic/edits.py /tmp/sidecar_example_run
```

An authoring file declares named inputs and returns typed edits without applying
them:

```python
from sidecar_edits import edits

REQUIRES = {
    "base": "base",
    "model_override": "assets/model_override.scs",
}

COMMON_PARAMS = {"corner": "tt"}

def edits_for(ctx):
    return [
        edits.copy_file(
            path=str(ctx.requires["model_override"]),
            to="include/model_override.scs",
        ),
        edits.replace(
            path="input.scs",
            old="corner=seed",
            new="corner={corner}",
        ),
    ]
```

Defaults in `REQUIRES` resolve next to the edit file. An embedding caller binds
resolved absolute paths by name:

```python
from sidecar_edits.render import materialize, resolve

plan = resolve(
    edit_path,
    requires={"base": base_path, "model_override": model_path},
    params={"corner": "ss"},
)
# plan.edits is complete and inspectable here.
materialize(plan, output_path)
```

See the [user guide](docs/user-guide.md) for requirements and edit authoring,
[parameter sets](docs/parameter-sets.md) for the three caller modes and identity
trade-offs, [examples](docs/examples.md) for every runnable command, and the
[API reference](docs/api.rst) for public Python signatures.

## Examples

```bash
sidecar-render examples/basic/edits.py /tmp/sidecar_basic
sidecar-render examples/apply_patch/edits.py /tmp/sidecar_patch
sidecar-render examples/param_matrix/edits.py /tmp/sidecar_matrix
sidecar-render examples/pwl_excel/edits.py /tmp/sidecar_pwl
```

The matrix example renders every named set and matrix point by default. Pass
`--run tt` to select one set before expansion. The Excel example declares its
workbook as `startup_table` and reads it only inside `edits_for(ctx)`.

## Verification and documentation

```bash
python -m pytest -q tests
python -m sphinx -b html docs docs/_build/html
```

From the parent repository, `python composition.py docs` builds the aggregate
documentation site.
