# Caller-owned render: one edit file, two clients

**Status: superseded 2026-08-25 by the broader caller-supplied authoring
redesign.** Its narrow override proposal was not built; its defect analysis,
hazards, and open questions remain the evidence that motivated the replacement.
Written 2026-08-24 from evidence found while binding the OTA/PVT study to
`sidecar_edits`. For what the code does today, read `docs/`.

Read the "What already works" section first. The caller-supplied `params` half of
this proposal is already how `render_job` behaves; the CLI is already one client
of that seam rather than its owner. What is missing is narrow: `BASE_DIR` is
resolved at load time, before a caller can say anything, and `COMMON_PARAMS` is
computed and discarded rather than offered to an embedding caller.

## The evidence

Binding `studies/ota_pvt.py` to this unit surfaced three things.

**The study imports an undeclared contract.** It does
`from sidecar_edits.render import load_editfile, render_job`. `ONTOLOME.md`
declares exactly three Python imports — `sidecar_edits`, `sidecar_edits.edits`,
`sidecar_edits.pwl`. `render` is not among them, has no docstrings, and appears
nowhere in `docs/` or `api.rst`. The study reached into a CLI's internals
because there was no published seam to reach for.

**The base directory is named twice.** The study declares
`docs/reference/ota-pvt-plan/inputs/base` as a hedloom `input_artifact`, so that
editing the base tree invalidates every point. The edit file separately declares
`BASE_DIR = "base"`, resolved against its own parent. Today the two agree by
coincidence of construction. Change `BASE_DIR` to `base_v2` and the work reads
one tree while the identity fingerprints another: edits to the tree actually
used stop invalidating anything, and edits to the abandoned one invalidate
everything.

**The sweep is defined twice.** `pvt_edits.py` carries `PARAM_SETS` with three
named PVT points. `ota_pvt.py` carries `PVT_POINTS` with the same three. The
study deliberately does not read `PARAM_SETS` — its `prepare_run` docstring says
values come from declared config "rather than re-read from the edit file's
`PARAM_SETS`, so a config edit and a rerun agree on what changed." One of the
two is dead data that still looks authoritative.

The second and third are the same defect: two components claim one
responsibility. `ONTOLOME.md` claims this unit owns "parameter sets and
matrices"; hedloom owns sweeps as its domain-generic core. The governing
manifesto forbids the result directly — capabilities must extend the reference
path "without hidden state or a second way to express the same intent."

## What already works

The seam is already split; one value landed on the wrong side of it.

`render_job(render_plan, params, output_dir, label)` substitutes the **caller's**
`params` into the edit templates, and never reads `render_plan.param_sets`. The
CLI's `main()` selects a named set and calls that same function. So the CLI and
an embedded study are already two clients of one entry point, and an authored
`edits.py` is already an override base: `EDITS` hold unsubstituted `{placeholder}`
templates, resolved at apply time from whoever is driving.

`BASE_DIR` is different only because `load_editfile` resolves it to a concrete
path at load time, before any caller exists. That is the whole defect. The fix is
to let a caller supply the resolved base, leaving every other load-time value
untouched, and to keep `common_params` on the `RenderPlan` so an embedding caller
can merge the file's invariants instead of restating them.

Backward compatibility is total: `overrides=None` is today's path exactly.

## The shape proposed

Not "make `render` private", and not "drop the CLI". One authored `edits.py`,
rendered by two clients:

    sidecar-render edits.py out --run tt_1v80_27c      # a shell, CI, an agent
    render(spec, params=..., base_dir=...)             # a hedloom operation

This is the manifesto's own shape rather than a concession to it. "Plain files
and CLI-first interfaces make the same capabilities available to an engineer at
a shell, a CI job, a script, or an agent", and "Operations are headless CLI and
Python entry points" — both halves, not a choice. The CLI and a study are two
replaceable clients of one contract, exactly as human-facing interfaces are
replaceable clients of the headless core.

What changes is authority, not capability. `PARAM_SETS` and `BASE_DIR` stop
being authorities and become the file's own defaults: the named variants this
setup ships with, for when no caller says otherwise.

## The distinction the algorithm turns on

An earlier form of this proposal said "replace, never merge" for every
overridable setting. That is too blunt, and the reason why is the useful part.

The edit file is itself a declared, fingerprinted input. A plain **value** that
comes from it is therefore already tracked: change `COMMON_PARAMS`, the file's
fingerprint changes, dependent work invalidates. Merging values is safe.

A setting that **locates another artifact** is different. `BASE_DIR` and
`COMMON_PARAMS_FILE` do not carry data; they select a file or tree whose content
is not otherwise declared. Fingerprinting the edit file catches the edit to
`BASE_DIR` itself, once. It cannot catch anything that later changes inside the
tree that `BASE_DIR` now points at, because nothing declared that tree.

So the rule is not about merging. It is:

> A caller that embeds this unit must own every setting that locates another
> artifact, because only the caller can declare that artifact to its own
> dependency tracking. Plain values may come from either side.

## Resolution algorithm

`load_editfile(path, overrides=None)`. `overrides` carries `params`,
`base_dir`, `copy_ignore` — all optional.

1. **`EDITS`** — from the file, always. Never overridable. It is the authored
   transformation; a caller that wants different edits wants a different file.

2. **`base_dir`** (artifact-locating) — if the caller supplies it, use it and do
   not consult `BASE_DIR`. Otherwise resolve `BASE_DIR` as today.

3. **`COMMON_PARAMS_FILE`** (artifact-locating) — an embedded caller must supply
   its resolved path as an override, so it can declare it as an input, or the
   file must inline `COMMON_PARAMS` instead. Silently reading an undeclared
   JSON file is the `BASE_DIR` defect wearing a different name.

4. **`params`** (values) — lowest to highest precedence:
   `COMMON_PARAMS` from the file, then the caller's `params`, per key. Merged,
   because the file is fingerprinted and its values are therefore tracked. This
   lets a file carry invariants a study need not restate.

5. **`PARAM_SETS` / `PARAM_MATRIX`** (variant enumeration) — not consulted at
   all when the caller supplies `params`. These enumerate variants, which is
   sweeping, which hedloom owns. Expanding them under an embedded caller would
   produce renders nobody asked for and reintroduce the second sweep engine.

6. **`copy_ignore`** — replaced if the caller supplies it.

Every resolved key records its source — file, named param set, or caller — in
provenance. Without that record the run carries state no reviewer can attribute,
which the manifesto's AI-assisted section rules out.

## The constraint on the caller

Whatever a hedloom operation overrides must come from **declared config**, not
from a local variable or module constant. Config is in the invocation identity;
a local is not. An override passed from a local is invisible to reuse: change
it, rerun, and every cached attempt still looks valid.

That constraint is what makes this a fix rather than a tidier arrangement of the
same defect. It belongs in the docstrings, not only here.

## Open points

**Whether `COMMON_PARAMS` should merge under caller params is not settled.**
The "Resolution algorithm" section above proposes merging, on the argument that
the edit file is fingerprinted and its literal values are therefore tracked. That
argument is sound but the ergonomics are not agreed: merging lets a file carry
invariants a study need not restate, and equally lets a value reach a render that
the study's author never read. Left open deliberately; do not treat step 4 as
decided.

**The algorithm covers declared settings, not import-time I/O.** This is a real
limit, found in `examples/pwl_excel/edits.py`:

    waveforms = pwl.waveforms_from_file(
        Path(__file__).parent / "waveforms" / "startup.xlsx", sheet="startup")

That path is not a module-level constant an override can substitute for. It is an
argument inside an expression evaluated during `runpy.run_path`, and the
spreadsheet's data is baked into an `EDITS` entry as a literal `content=` string
before any caller exists. No `overrides` key can reach it.

It also refutes the premise that values from the edit file are safe because the
file is fingerprinted. That holds for values *literal in the file*. A file that
*reads* another file escapes it: edit `startup.xlsx`, the edit file's bytes are
unchanged, its fingerprint is unchanged, and dependent work is not invalidated.
Same defect as `BASE_DIR`, without even a constant to notice.

Three responses, in increasing order of work:

1. **Declare, do not override.** An embedding caller declares `startup.xlsx` as
   its own input artifact beside the edit file. Fingerprinting becomes correct;
   substitution remains impossible. Correct today with no API change, but a
   caller can only discover the requirement by reading the edit file.
2. **`def render(ctx)`** — the procedural interface already proposed in
   `brainstorming.md`, which names spreadsheet-driven generation as its
   motivation. Moves the read to apply time where a caller can reach it, at the
   cost that unit's own note records: the renderer can no longer inspect the full
   edit plan before applying it.
3. **Defer content, keep `EDITS` declarative.** Let `content=` accept a callable
   receiving the render context, and add a declared, overridable data mapping —
   `DATA = {"startup": "waveforms/startup.xlsx"}` — resolved like `BASE_DIR`. The
   edit list stays inspectable while the spreadsheet moves to apply time. This
   appears to take (2)'s laziness without (2)'s drawback, and is the direction
   this note favours.

Until one is built, `pwl_excel`-shaped edit files are usable from a study only
under (1), and that constraint belongs in the docstrings.

**Why are these paths at all?** `BASE_DIR`, `COMMON_PARAMS_FILE` and the
spreadsheet in `pwl_excel` are each the edit file stating *where* something is.
An edit file arguably should only state *what* it needs, leaving location to
whoever renders it. Hedloom already works that way: an `@operation` declares
`inputs={"base": SIDE_CAR_BASE}` and receives resolved paths, rather than
hardcoding them.

The equivalent here would be a named requirement declared by the edit file --
`REQUIRES = {"base": ..., "startup_table": ...}` -- with binding owned by the
caller: the CLI binds from defaults beside the edit file, a study binds from its
declared artifacts. Three properties fall out together. Every external
dependency becomes enumerable without reading the file's logic. Nothing can be
read that was not handed over, which closes the import-time I/O hole above rather
than working around it. And `BASE_DIR`, `COMMON_PARAMS_FILE` and arbitrary data
files stop being three special cases with three rules.

It would also make an edit file a pure transformation: what to do, never where
the world is. That is the property that makes one file genuinely serve both
clients, rather than serving both with caveats. Not proposed as work here, but
the override design above is a narrower answer to the same question, and should
not be built in a way that forecloses this one.

**Does a render context deliver all three responses at once?** Probably, and
more cheaply than the three-way split above suggests. `RenderContext` already
exists as a Protocol and is already threaded to every `edit.apply(context)`;
what is missing is passing it to deferred callables and giving it resolved named
inputs to carry. With that, response (3) is "content callables receive ctx",
response (2) is the same mechanism at whole-file granularity, and response (1)
stops being caller discipline: a study can enumerate declared requirements
instead of reading the edit file and inferring what it touches.

Two things a context does not settle. It does not decide granularity, and that
choice has consequences -- whole-file deferral loses the pre-apply edit plan, and
with it dry run and plan review, which the governing manifesto asks for by name
("materialize inspectable jobs and dependencies before spending simulation
resources"). Per-content deferral keeps them. And a context is only worth
building if it carries *declared* inputs; one that merely exposes `editfile_dir`
leaves the file free to read whatever it likes, delivering the mechanism without
the property it was for.

**The override channel creates a plan-time hazard that does not exist today.**
If a study reads a value out of the edit file while composing its plan -- by
importing it, or by `runpy` -- that value is frozen into the Plan's declarations
and its invocation identity. The override then changes what the render actually
uses. Plan and render diverge, and nothing compares them.

This is not a pre-existing defect. Before an override channel, the edit file's
value was the only value, so deriving from it at plan time was consistent. The
feature is what makes the derivation unsafe, which is a reason to state the rule
in the same change that adds the channel, not later.

The guard already exists in this repository, applied to one file:
`integration-tests/test_ota_pvt_plan_reference.py` monkeypatches `open`,
`io.open`, `os.open`, `Path.open`, `Path.read_bytes` and `Path.read_text` to
refuse, and separately asserts the plan module's imported roots are exactly
`{"__future__", "hedloom_flow", "dataclasses"}`. Both halves of the hazard are
covered: `runpy.run_path` trips the first, `from pvt_edits import BASE_DIR` trips
the second. What is missing is that this is enforced as one file's test rather
than stated as a property studies are expected to hold.

Two rules, in priority order:

1. **Planning reads no files.** A study composes its plan from addresses, not
   from the content of the things it addresses.
2. **If a value genuinely must be known at plan time, obtain it from
   `load_editfile` with the same inputs the render will use** -- never by
   importing the edit file. One resolver, one answer, agreement by construction.
   The cost is that planning then touches the filesystem and rule 1 is lost,
   which is why this is the fallback.

An earlier draft of this thinking recommended deriving the study's base locator
from the edit file's `BASE_DIR` so the two could not disagree. Under an override
channel that recommendation inverts: deriving at plan time is precisely the
divergence it was meant to prevent.

## What this does not do

It does not narrow `ONTOLOME.md`'s claim on "parameter sets and matrices". The
claim becomes accurate rather than contested — this unit owns named variants for
its CLI; an embedding caller owns variant selection. If that proves too subtle
in use, the harder change is to drop variant enumeration from this unit
altogether and let hedloom own sweeps outright. This proposal is deliberately
the reversible step before that one.

It also does not document `render`. Publishing the current signatures would
freeze an accidental shape. The docstrings, the `api.rst` entry and the
`ONTOLOME.md` contract line should be written against the seam above, once it
exists.
