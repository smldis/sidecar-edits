# Internals

For working *on* the package rather than with it. Nothing here is needed to
author an edit file — that is [the user guide](user-guide.md).

## Edit File Execution

The edit file is a Python file. The renderer executes it first, reads the
resulting `BASE_DIR`, parameter definitions, and `EDITS`, and only then applies
the edit operations for each selected run.

This keeps setup code, imports, local helper functions, and data loading in the
normal Python execution model without introducing a separate compilation step.

## Implementation Model

Each edit helper returns a frozen, operation-specific edit object. For example, a
replace operation has typed attributes `path`, `old`, `new`, `allow_no_match`,
`description`, and `source_stack`.

Edit objects execute through `apply(context)`. The render context provides the
target run directory, edit file directory, edit file path, and current
parameters.

Operation implementations should read typed attributes from the edit object. Do
not use generic dictionary field bags for the public edit model.

## Error Reporting

An operation raises `EditError` describing only what it knows. The renderer adds
the envelope: the `EDITS[index]` position, the operation name, the description if
there is one, and the source location captured when the edit object was created.

```text
error: EDITS[3] replace "select corner netlist" failed
created at edits.py:18 in <module>
reason: replace target not found in /tmp/run/input_main.scs
```

The source stack is captured at construction rather than at application, so an
edit built inside a helper function reports the whole short chain:

```text
error: EDITS[1] replace failed
created at helpers/netlist.py:7 in model_include
called from edits.py:15 in <module>
reason: replace target not found in /tmp/run/input.scs
```

This is not intended to be a full Python traceback. The renderer should show only
the small amount of source context needed to find the edits.

## Maintainer Rules

- Keep edit helpers in the `sidecar_edits.edits` namespace.
- Give each helper a typed keyword-only signature and a concise docstring.
- Keep `description` optional.
- Capture source locations when edit objects are created, not when they are
  applied.
- Keep ordinary edit failures as `EditError` and let the renderer add the common
  `EDITS[index]` and source-location envelope.
- Prefer construction-time tracing over AST parsing. The renderer executes the
  edit file before applying edit operations.
- Do not accept raw dictionary entries in `EDITS`.

## Building This Documentation

Generated HTML is intentionally ignored. Build it reproducibly from the
unit-owned source:

```bash
python -m pip install -e ".[docs]"
python -m sphinx -b html docs docs/_build/html
```

Preview it with:

```bash
python -m http.server --directory docs/_build/html 8000
```

From the parent repository, `python composition.py docs` instead builds the root
glue and all immediate child documentation into `build/docs/html/`.

## Checks

```console
python -m pytest -q tests
```
