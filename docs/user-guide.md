# User Guide

An edit file names every external input it needs and defines one function that
builds typed file transformations. Building the list and applying it are
separate operations, so a Python caller can inspect the complete plan before
anything writes to the output directory.

## Authoring contract

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
            description="select process corner",
        ),
    ]
```

`edits_for(ctx)` returns or yields `sidecar_edits.edits` objects. It does not
apply them. There is no alternate module-level list or procedural render
function. Returning data preserves review, dry-run inspection, source tracing,
and the ability to refuse an invalid plan before the base tree is copied.

The factory receives:

- `ctx.requires`: every declared requirement as a resolved `Path`;
- `ctx.params`: the one resolved variant's parameter mapping; and
- `ctx.declarations`: the effective declaration mapping, including any
  whole-value replacements supplied by a caller.

Constructing edit objects captures the source stack. A helper called inside
`edits_for` therefore still reports both the helper line and its factory caller.
Raw dictionary edits are rejected.

## Named external inputs

`REQUIRES` maps stable names to CLI defaults. Defaults resolve relative to the
edit file after parameter and environment formatting.

```python
REQUIRES = {
    "base": "base",
    "startup_table": "waveforms/startup.xlsx",
    "site_model": None,
}
```

`base` is mandatory because every render copies one authoritative base tree.
`None` means there is no CLI default: a caller must bind that name. Python
callers bind resolved absolute paths through `resolve(..., requires={...})`.
Passing an undeclared name, a relative caller path, or omitting a name with no
default raises `EditError`.

Requirements are enumerable from `read(path).requirement_defaults` before the
factory runs. Adding a new requirement is additive: it uses the same name-keyed
mapping and appears in `ctx.requires`; there is no second path channel.

## Python embedding

```python
from sidecar_edits.render import materialize, read, resolve, variants

authored = read(edit_path)
available = variants(authored)  # data only; does not build or apply edits

plan = resolve(
    authored,
    requires={"base": base_path.resolve()},
    selector="ss_1v62_125c",
)
inspect(plan.edits)
materialize(plan, output_path, label="ss_1v62_125c")
```

`resolve` always produces exactly one variant. Embedding clients create their
own invocations and call it once per invocation; only the CLI loops over sets or
matrix points. See [Parameter Sets and Matrices](parameter-sets.md) for explicit
parameters, selectors, supplied definitions, and their reuse identity.

## PWL tables without import-time I/O

External tables are requirements and are read inside the factory:

```python
from sidecar_edits import edits, pwl

REQUIRES = {
    "base": "base",
    "startup_table": "waveforms/startup.xlsx",
}

def edits_for(ctx):
    waveforms = pwl.waveforms_from_file(
        ctx.requires["startup_table"], sheet="startup"
    )
    source_lines = "\n".join(
        f"V{name} {name} 0 {waveform.render_pwl()}"
        for name, waveform in waveforms.items()
    ) + "\n"
    return [
        edits.write_file(
            path="generated/pwl_sources.inc",
            content=source_lines,
            description="generate startup sources",
        ),
        edits.append_to_file(
            path="input.scs",
            content='include "generated/pwl_sources.inc"\n',
        ),
    ]
```

Importing this file defines declarations and the function; it does not open the
workbook. Resolving it hands the factory the declared path and fingerprints can
track that same artifact at an embedding boundary.

The PWL table's first header must be `#time`; remaining headers name waveforms.
Blank cells omit points. Values remain SPICE text. `waveforms_from_text` accepts
delimited text, and `waveforms_from_file` accepts delimited files or workbooks.

## Edit operations

The `sidecar_edits.edits` namespace exposes typed helpers for:

- `extract_subckts`, `copy_file`, `rename_file`, `write_file`, and `append_to_file`;
- `insert_series_source_at_instance_net`;
- `replace` and `regex_replace`; and
- `run`, `patch`, and `apply_patch`.

Every operation is a file transformation. `run`, `patch`, `apply_patch`, and the
extraction helper reach an external tool to perform one, and `run` is the escape
hatch for a transformation this vocabulary does not name -- a site's own netlist
munger, an awk one-liner, a generator script. It is not a way to launch
simulators or evaluate results: those run a materialized directory rather than
building one, and belong to the execution component.

What `run` gives up is inspection. A resolved plan shows the command it will
execute, not what that command will do, so a plan carrying one is reviewable
only as far as the command name. Prefer a named operation wherever one fits, and
keep the command a pure function of the run directory.

`copy_file` requires an absolute source path obtained from `ctx.requires`.
`rename_file` instead selects a file the base copy already placed in the
rendered tree: its `pattern` is a regular expression matched with `re.fullmatch`
against paths relative to the run directory, exactly one file must match, and
the edit names the candidates when several do. That pattern is used verbatim,
so quantifiers such as `{1,3}` are not read as parameter fields; the
destination is formatted normally and then expanded against the match, so `\1`
carries a captured group into the new name.
Destination and target paths are inside the rendered tree. Parameter formatting
uses `{name}` fields. Path fields additionally expand environment variables;
replacement content does not, preserving simulator-side variables.

Edits fail by default. The command, patch, and extraction operations accept
`optional=True` only when skipping is genuinely valid. Text replacement accepts
`allow_no_match=True` for an intentionally absent target.

## Error reporting

A failed edit reports its factory result index and construction stack:

```text
error: edits_for(ctx)[1] replace "select corner" failed
created at helpers/netlist.py:7 in model_include
called from edits.py:15 in edits_for
reason: replace target not found in /tmp/run/input.scs
```

Paths beneath the edit-file tree are displayed relative to it; outside paths
remain absolute.
