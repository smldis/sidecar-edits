# Internals

For working on the package rather than authoring an edit file.

## Resolution pipeline

The public path has four explicit stages:

1. `read(path, declarations=...)` executes the file only to collect declarations
   and its `edits_for` function. Caller declarations replace whole authored
   declarations through the same generic mapping.
2. `variants(edit_file)` expands parameter sets and matrices as data. The CLI
   uses this stage to decide what it will loop over.
3. `resolve(...)` binds declared requirement names, resolves one selector or
   explicit parameter mapping, and calls `edits_for(ctx)`. It validates and
   stores the complete typed edit tuple in `RenderPlan`.
4. `materialize(plan, output)` copies the base and applies that tuple.

The separation is a contract: no output write occurs while the complete list is
being built, and an embedding caller—not the renderer—owns invocation fan-out.

## Declaration layer

The `declarations` argument is a mapping keyed by the same uppercase names as
the edit file. The overlay itself has no per-declaration API: each supplied
value replaces the authored value. Validators then interpret `REQUIRES`,
`COMMON_PARAMS`, `PARAM_SETS`, `PARAM_MATRIX`, and `COPY_IGNORE`. A later
declaration uses this same channel and appears in `ctx.declarations`.

Requirement bindings are deliberately separate. Declarations say which names
exist and give CLI defaults; bindings hand a particular caller's resolved paths
to those names. Unknown, relative, or missing bindings fail before the factory
runs.

## Typed edits and tracing

Each helper returns a frozen operation-specific object. `edits_for(ctx)` may
return any iterable, which `resolve` consumes once into a tuple. Raw dictionaries
are rejected.

Construction captures a short `SourceFrame` stack. Applying an edit later does
not erase where it was declared: the materializer reports
`edits_for(ctx)[index]`, operation, description, helper construction line, and
factory caller. Keep tracing at construction time when adding helpers.

Edit objects apply through an internal context carrying the target directory,
edit-file path, one parameter mapping, and resolved requirements. Operations
must remain file transformations. Simulator/workflow launch belongs outside the
unit. The extraction helper and patch tools may shell out only to transform the
materialized files described by their edit objects.

## Maintainer rules

- Keep helpers typed, keyword-only, documented, and in `sidecar_edits.edits`.
- Keep `description` optional and ordinary failures as `EditError`.
- Preserve the pre-materialization `RenderPlan` and source stack.
- Add external input names to `REQUIRES`; do not introduce path constants or
  file-backed parameter shortcuts.
- Embedded resolution produces one variant. The CLI may loop; libraries and
  operations must not hide a sweep.
- Keep edit files import-safe: module execution defines declarations and the
  factory, while input reads occur inside `edits_for(ctx)`.

## Checks

```console
python -m pytest -q tests
python -m sphinx -b html docs docs/_build/html
```
