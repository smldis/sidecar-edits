# Sidecar Edits

Prototype tooling for resolving named inputs and typed file transformations into
repeatable analog simulation run directories.

The authoring file defines one factory that returns inspectable edits. Resolution
builds the complete single-variant plan; materialization then copies the base and
applies it. The CLI may loop over authored variants.

```python
from sidecar_edits import edits

REQUIRES = {"base": "base"}

def edits_for(ctx):
    return [
        edits.replace(
            path="input.scs",
            old="parameters corner=seed",
            new="parameters corner=tt",
        ),
    ]
```

## Quick Start

Install the package in editable mode:

```bash
python -m pip install -e .
```

Render the basic example:

```bash
sidecar-render examples/basic/edits.py /tmp/sidecar_example_run
```

## Start here

| If you want to | Read |
| --- | --- |
| author an edit file, format parameters, inject sources, read errors | [User guide](user-guide.md) |
| choose explicit params, selectors, supplied definitions, or CLI matrices | [Parameter sets and matrices](parameter-sets.md) |
| see it working end to end, including Excel-backed PWL sources | [Examples](examples.md) |
| look up authoring, rendering, edit, or PWL signatures | [API reference](api.rst) |
| work *on* this package rather than with it | [Internals](internals.md) |

```{note}
This project is intentionally small and text-first. It favors explicit,
reviewable edits over a full simulator netlist model.
```

```{toctree}
:maxdepth: 2
:caption: Using Sidecar Edits

user-guide
parameter-sets
examples
api
```

```{toctree}
:maxdepth: 2
:caption: Working on Sidecar Edits

internals
```
