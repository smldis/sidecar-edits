# Sidecar Edits Ontology

## Purpose and scope

Sidecar Edits turns named input paths and typed Python edit declarations into
inspectable single-run plans and materialized simulation directories. It owns
edit-file authoring and resolution, named parameter variants, traced pure
file transformations, PWL table generation, and the native subcircuit
extraction helper used by those transformations.

## Mode of being

**Development state:** `prototype`

Its present runnable form studies which typed, inspectable edit operations and
parameter conventions can replace repeated manual simulation-directory setup
without taking authority from the authored base. Real examples, skipped or
failed edits, and awkward preparation flows are evidence for revising the API,
the materialization boundary, or this account of the unit. The capability is
useful now, but its current operation set and packaging are not presumed final;
extensions should remain explicit, reversible, and tested in proportion to
their risk.

## Current contracts

- Python imports: `sidecar_edits`, `sidecar_edits.edits`,
  `sidecar_edits.pwl`, and `sidecar_edits.render`.
- Authoring: an edit file declares `REQUIRES` and defines exactly
  `edits_for(ctx) -> Iterable[EditSpec]`; resolving it returns a complete edit
  tuple before materialization writes output. The iterable may be a returned
  list or a generator; generators are the authoring form for conditional or
  computed edits.
- Python rendering: `sidecar_edits.render.read`, `variants`, `resolve`, and
  `materialize`, with caller declarations supplied through one replacement
  mapping and requirement paths bound separately by declared name.
- CLI: `sidecar-render`.
- Authored inputs: a Python edit file and the external files or trees named by
  its effective `REQUIRES` declaration.
- Materialized output: copied and edited run directories; the base remains
  authoritative.
- Build contract: the C helper source is package data and is compiled by the
  package build or lazily through the installed package.

## Contribution to the parent

The unit contributes a reviewable, headless preparation operation for simulation
inputs. Its examples demonstrate the current end-to-end slice.

## Exclusions

It does not parse a canonical circuit graph, decompose circuit function, launch
simulators or arbitrary commands as edits, evaluate results, expand embedded
study invocations, schedule studies, or own project-wide policy.

## Child composition

There are currently no child units.
