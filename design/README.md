# Design record — working material, not documentation

Nothing in this directory is published or maintained. `composition.py docs`
stages only `sidecar-edits/docs/`, so these files never reach the Sphinx site,
and that is the point: they are dated notes about a shape the code has since
taken, or declined to take. **They record what was proposed, not what the code
now does.** For what the code now does, read `docs/`.

Kept rather than deleted because the argument behind an interface outlives the
interface, and because one of these still holds an unbuilt proposal someone may
pick up.

## What is here

| File | What it is | Status |
| --- | --- | --- |
| `brainstorming.md` | Two per-section idea notes written while the prototype was taking shape: named parameter sets, and an alternative render-context script interface. | Split. Named parameter sets are **delivered** — the maintained account is `docs/parameter-sets.md`. The `def render(ctx)` procedural interface is a **live proposal, deliberately not built**; `EDITS = [...]` stays the only interface. |
| `pwl-table-sources.md` | The proposal for turning spreadsheet-authored waveform tables into SPICE `PWL(...)` expressions: table format, loaders, object model, wrapping, validation. | **Delivered** as `sidecar_edits.pwl`, with `examples/pwl_excel/` and `tests/test_pwl_table_sources.py`. Its own "Status: Draft." line was already false when this file moved here. The maintained account is the PWL Tables section of `docs/user-guide.md`. |

A third page, `edits-api.md`, used to live beside these. It was reference
documentation rather than a proposal, and was promoted to `docs/internals.md`
instead of being archived here.

## The rule

A file here is never edited to stay true. If something in it is now wrong, that
is expected — it was written before the code caught up. If something in it is
still right and load-bearing, it belongs in `docs/` or in `ONTOLOME.md`, not
here.
