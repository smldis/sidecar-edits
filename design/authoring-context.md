# Caller-supplied authoring context

**Status at writing: proposed and implemented together on 2026-08-25.** This is
a dated design record, not maintained documentation. Current behavior belongs
in `docs/` and `ONTOLOME.md`.

## Evidence

The OTA/PVT embedding reached into an undocumented renderer, separately named
the base tree for work and identity, and could not account for files read while
an edit module was imported. The Excel PWL example demonstrated the last defect:
changing its workbook changed rendered content without changing the edit file's
fingerprint. Arbitrary command execution also made preparation partly an
executor, contrary to the unit boundary.

The earlier caller-owned-render note proposed special overrides on the existing
shape. Its analysis stood, but a path-by-path override layer would preserve
multiple artifact-location mechanisms and leave import-time work possible.

## Proposed contract

An edit file has one authoring entry point:

```python
def edits_for(ctx):
    return [edits.replace(...)]
```

It builds an iterable of typed edit specs and never applies them. This is not
the earlier `def render(ctx)` proposal. Returning data lets a caller inspect the
complete transformations before materialization, while a procedural render
would discover edits only while performing them.

External inputs are declared by stable name:

```python
REQUIRES = {"base": "base", "startup_table": "waveforms/startup.xlsx"}
```

Defaults are CLI conveniences resolved beside the edit file. An embedding
caller binds absolute paths by name, and the same resolved mapping reaches the
factory as `ctx.requires`. Unknown names and names with neither binding nor
default fail before edit construction.

## One declaration channel

Anything the file can declare can be supplied by a caller through one mapping
keyed by the same uppercase names. Supplied values replace whole declarations;
they do not merge. This applies to requirements, common parameters, parameter
sets, and matrices, and avoids adding an API argument for each future
declaration. Requirement path binding remains separate from declaration because
one defines the names while the other supplies artifacts for one invocation.

## Variant ownership and identity

The CLI expands sets and matrices because looping is its operation. An embedded
resolve produces one variant; a study authors the sweep as invocations.

Three inputs are supported. Explicit parameters give fine-grained identity but
restate point values. A selector keeps one authored definition but combines its
config name with the edit-file fingerprint, so file edits invalidate every
dependent point. Supplied set definitions replace the file's sets and combine
with a separate selector; their values are safe only when the entire definition
is declared caller config. Fine-grained identity requires a one-item replacement
per invocation, so another corner's definition is absent from that invocation's
config. A local value outside config is invisible to reuse.

Variant expansion is also exposed as data. This permits a study with
caller-owned definitions to expand exactly the same declarations at plan time
without reading the edit file. Reading an edit file while composing a Plan is
otherwise prohibited: plan declarations can freeze one value while rendering
later resolves another, and no contract compares them.

## Boundary consequences

Arbitrary command edits are removed. The remaining operations transform files;
simulator and workflow launch stays in Hedloom. Parameter JSON locators are also
removed because literal set values are fingerprinted with the edit file, while
external files must travel through named requirements.

Source-stack capture remains at edit construction. Moving construction inside
the factory changes the reported caller from module scope to `edits_for`, but
preserves the human- and agent-facing line that declared each failing edit.
