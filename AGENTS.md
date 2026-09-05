# Sidecar Edits agent guidance

Inherit the project guidance from `../AGENTS.md`. Before work here, read
`../MANIFESTO.md`, `../ONTOLOME.md`, local `ONTOLOME.md`, local `README.md`, and
local `unit.toml`, then inspect the relevant implementation and tests.

This unit owns typed edit declarations and their reviewable materialization
from an authoritative base into simulation run directories, including its
parameter, file/text, PWL, and native-helper behavior. Keep simulator execution,
canonical parsing, functional decomposition, and project policy outside this
boundary. Update the local ontology when this being changes; place a changed
contract with another unit in the closest containing ontology.

## Where to read, and what to trust

Three surfaces, deliberately separate. Know which one you are in.

| Surface | Where | Maintained against the code? |
| --- | --- | --- |
| **Self-study** — evolving understanding, including commitments, evidence, assumptions, and open questions | `ONTOLOME.md` | **Yes.** Refine it when work yields useful insight; update commitments explicitly when they change. Repo-native, not published. |
| **Documentation** — how to use it and how it works | `docs/` | **Yes.** Everything under `docs/` is published to the Sphinx site by `python composition.py docs` from the repository root. |
| **Design record** — proposals and dated idea notes | `design/` | **No.** Written on a date, never edited to stay true, never published. |

The rule that follows: **do not cite a `design/` file as evidence of current
behaviour, and do not update one to match the code.** If something in there is
still right and load-bearing, promote it into `docs/` or `ONTOLOME.md`.
`design/README.md` says which is which — today one proposal is live, the
`def render(ctx)` procedural edit-file interface in `design/brainstorming.md`,
and it is deliberately not built. Everything else there is delivered.

Never link a published page to `design/` or `ONTOLOME.md`: Sphinx cannot resolve
it and the build warns. Name such files as inline code instead.

A page reachable by URL but absent from a `{toctree}` in `docs/index.md` is
unreachable in practice. Add both when you add a page.

## Checks

```console
python -m pytest -q tests
python ../composition.py docs          # from the repository root: python composition.py docs
```

A successful Sphinx build can still report missing toctree entries and
unresolved cross-references, so read the warnings rather than the exit status.
