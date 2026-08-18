# Sidecar Edits

Prototype tooling for building repeatable analog simulation runs from a base
directory and a small Python sidecar.

The renderer executes an edit file, copies the base tree, applies typed edit
operations, and writes one or more concrete run directories. The suggested edit
file name is `edits.py`, and the interface is plain Python while still providing
source-location error reports.

```python
from sidecar_edits import edits

BASE_DIR = "base"

EDITS = [
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
| render many runs from one file: corners, sweeps, output layout | [Parameter sets and matrices](parameter-sets.md) |
| see it working end to end, including Excel-backed PWL sources | [Examples](examples.md) |
| look up a helper's signature or a PWL type | [API reference](api.rst) |
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
