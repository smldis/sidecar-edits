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
| `brainstorming.md` | Two per-section idea notes written while the prototype was taking shape: named parameter sets, and an alternative render-context script interface. | Split. Named parameter sets were delivered. The procedural `def render(ctx)` proposal was **superseded** on 2026-08-25 by a factory that returns inspectable edit specs instead of applying them. |
| `pwl-table-sources.md` | The proposal for turning spreadsheet-authored waveform tables into SPICE `PWL(...)` expressions: table format, loaders, object model, wrapping, validation. | **Delivered** as `sidecar_edits.pwl`, with `examples/pwl_excel/` and `tests/test_pwl_table_sources.py`. Its own "Status: Draft." line was already false when this file moved here. The maintained account is the PWL Tables section of `docs/user-guide.md`. |

| `caller-owned-render.md` | A narrow published render seam so one `edits.py` serves both the CLI and an embedding caller; its defect analysis found duplicated artifact and sweep authority. | **Superseded, not built.** The 2026-08-25 redesign kept its evidence but replaced its special-case override proposal with named requirements and one declaration channel. |
| `authoring-context.md` | The 2026-08-25 proposal for one `edits_for(ctx)` factory, named requirements, caller-supplied declarations, three identity-aware variant modes, and single-variant embedding. | **Delivered by the same breaking 0.2 change.** The maintained contract is in `ONTOLOME.md` and `docs/`. |

A third page, `edits-api.md`, used to live beside these. It was reference
documentation rather than a proposal, and was promoted to `docs/internals.md`
instead of being archived here.

## The rule

A file here is never edited to stay true. If something in it is now wrong, that
is expected — it was written before the code caught up. If something in it is
still right and load-bearing, it belongs in `docs/` or in `ONTOLOME.md`, not
here.
