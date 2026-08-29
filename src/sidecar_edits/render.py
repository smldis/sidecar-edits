#!/usr/bin/env python3

"""Load, resolve, inspect, and materialize Sidecar Edits authoring files.

An edit file declares metadata and defines ``edits_for(ctx)``. Reading the file
does not build edits. Resolving it binds named requirements and exactly one
variant, then calls ``edits_for`` to produce a complete, inspectable
:class:`RenderPlan`. :func:`materialize` is the only step that writes a run
directory.
"""

from __future__ import annotations

import argparse
import fnmatch
import itertools
import os
import re
import runpy
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from sidecar_edits import edits as edits_api
from sidecar_edits import tool_path

if __name__ == "__main__":
    sys.modules["sidecar_edits.render"] = sys.modules[__name__]


class EditError(RuntimeError):
    """Raised when an authoring file, edit, or materialization is invalid."""


@dataclass(frozen=True)
class ParamSet:
    """One declared named parameter set, before matrix expansion."""

    name: str | None
    params: dict[str, object]
    description: str | None = None
    targetdir: str | None = None


@dataclass(frozen=True)
class Variant:
    """One fully expanded authored variant, available without rendering."""

    name: str | None
    selector: str | None
    params: dict[str, object]
    description: str | None = None
    targetdir: str | None = None
    matrix_suffix: str | None = None


@dataclass(frozen=True)
class EditFile:
    """An edit file's effective declarations and authoring entry point.

    ``declarations`` includes whole-value replacements supplied by a caller.
    Passing caller declarations from an embedding operation is safe for reuse
    only when the entire mapping is declared operation config. A module constant
    or local value that bypasses declared config is invisible to reuse.
    """

    path: Path
    declarations: dict[str, object]
    requirement_defaults: dict[str, str | os.PathLike[str] | None]
    common_params: dict[str, object]
    param_sets: tuple[ParamSet, ...]
    param_matrix: dict[str, list[object]]
    copy_ignore: tuple[str, ...]
    edit_factory: Callable[[AuthoringContext], Iterable[edits_api.EditSpec]]

    @property
    def directory(self) -> Path:
        """Directory containing the authored edit file."""

        return self.path.parent


@dataclass(frozen=True)
class AuthoringContext:
    """Resolved values handed to ``edits_for(ctx)`` while building a plan.

    ``requires`` contains only declared, resolved paths. ``params`` contains the
    one selected variant's parameters. ``declarations`` exposes the effective
    declaration mapping so future declarations use the same caller-supply
    channel rather than adding another mechanism.
    """

    requires: Mapping[str, Path]
    params: Mapping[str, object]
    declarations: Mapping[str, object]


@dataclass(frozen=True)
class RenderPlan:
    """A complete, inspectable single-variant plan ready to materialize."""

    editfile_path: Path
    requires: dict[str, Path]
    params: dict[str, object]
    copy_ignore: tuple[str, ...]
    edits: tuple[edits_api.EditSpec, ...]
    selector: str | None = None

    @property
    def base_dir(self) -> Path:
        """Resolved base-tree requirement used by materialization."""

        return self.requires["base"]

    @property
    def editfile_dir(self) -> Path:
        """Directory containing the authored edit file."""

        return self.editfile_path.parent


@dataclass(frozen=True)
class RenderContext:
    target_dir: Path
    editfile_dir: Path
    editfile_path: Path
    params: dict[str, object]
    requires: dict[str, Path]


@dataclass(frozen=True)
class LogicalStatement:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class MatrixCase:
    suffix: str | None
    params: dict[str, object]


PARAM_SET_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DECLARATION_DEFAULTS: dict[str, object] = {
    "COPY_IGNORE": (),
    "COMMON_PARAMS": {},
    "PARAM_SETS": None,
    "PARAM_MATRIX": {},
}
_REMOVED_DECLARATIONS = {"BASE" + "_DIR", "ED" + "ITS", "COMMON_PARAMS_FILE"}


def read(
    editfile_path: str | os.PathLike[str],
    *,
    declarations: Mapping[str, object] | None = None,
) -> EditFile:
    """Read an authoring file without building edits or touching an output.

    ``declarations`` is the uniform caller-supply channel. Its uppercase keys
    replace whole declarations from the file; values are never merged. This
    includes ``REQUIRES``, ``COMMON_PARAMS``, ``PARAM_SETS`` and
    ``PARAM_MATRIX``, and the same mapping carries later declarations.

    Supplied values affect reuse identity only if an embedding operation
    declares the entire mapping as config. Passing definitions from a module
    constant or local variable outside declared config makes changes invisible
    to reuse and is therefore invalid caller usage.
    """

    path = Path(editfile_path).resolve()
    loaded = runpy.run_path(str(path))
    removed = sorted(_REMOVED_DECLARATIONS.intersection(loaded))
    if removed:
        raise EditError(f"{path} uses removed declaration(s): {', '.join(removed)}")

    edit_factory = loaded.get("edits_for")
    if not callable(edit_factory):
        raise EditError(f"{path} must define edits_for(ctx)")

    authored = {
        name: value
        for name, value in loaded.items()
        if isinstance(name, str) and name.isupper() and not name.startswith("_")
    }
    effective = dict(_DECLARATION_DEFAULTS)
    effective.update(authored)
    if declarations is not None:
        for name, value in declarations.items():
            if not isinstance(name, str) or not name.isupper():
                raise EditError(f"caller declaration names must be uppercase strings: {name!r}")
            if name not in authored and name not in _DECLARATION_DEFAULTS and name != "REQUIRES":
                raise EditError(f"caller supplied undeclared declaration: {name}")
            effective[name] = value

    requirement_defaults = _load_requirements(path, effective.get("REQUIRES"))
    common_params = _load_common_params(path, effective.get("COMMON_PARAMS"))
    param_sets = tuple(_load_param_sets(path, effective.get("PARAM_SETS"), common_params))
    param_matrix = _load_param_matrix(path, effective.get("PARAM_MATRIX"))
    copy_ignore = _load_copy_ignore(path, effective.get("COPY_IGNORE"))
    return EditFile(
        path=path,
        declarations=effective,
        requirement_defaults=requirement_defaults,
        common_params=common_params,
        param_sets=param_sets,
        param_matrix=param_matrix,
        copy_ignore=copy_ignore,
        edit_factory=edit_factory,
    )


def variants(source: EditFile | Mapping[str, object]) -> tuple[Variant, ...]:
    """Return fully expanded authored variants as data, without rendering.

    Pass an :class:`EditFile` to inspect file-authored definitions, or pass a
    declarations mapping to resolve caller-owned definitions without reading an
    edit file. The CLI uses this same expansion before it loops over outputs.

    A study should not read an edit file while composing a Plan: those values
    would be frozen into Plan declarations while a later render could resolve
    different values. If plan-time variants are genuinely required, call this
    resolver with the exact caller declarations that the render receives.
    """

    if isinstance(source, EditFile):
        param_sets = source.param_sets
        param_matrix = source.param_matrix
    elif isinstance(source, Mapping):
        label = Path("<caller declarations>")
        common = _load_common_params(label, source.get("COMMON_PARAMS", {}))
        param_sets = tuple(_load_param_sets(label, source.get("PARAM_SETS"), common))
        param_matrix = _load_param_matrix(label, source.get("PARAM_MATRIX", {}))
    else:
        raise TypeError("variants source must be an EditFile or declarations mapping")

    expanded: list[Variant] = []
    for param_set in param_sets:
        for case in expand_param_matrix(param_matrix):
            name = param_set.name
            if case.suffix:
                name = f"{name}__{case.suffix}" if name else case.suffix
            expanded.append(
                Variant(
                    name=name,
                    selector=param_set.name,
                    params=param_set.params | case.params,
                    description=param_set.description,
                    targetdir=param_set.targetdir,
                    matrix_suffix=case.suffix,
                )
            )
    return tuple(expanded)


def resolve(
    editfile: str | os.PathLike[str] | EditFile,
    *,
    requires: Mapping[str, str | os.PathLike[str]] | None = None,
    params: Mapping[str, object] | None = None,
    selector: str | None = None,
    declarations: Mapping[str, object] | None = None,
) -> RenderPlan:
    """Resolve exactly one inspectable render plan without writing output.

    ``params`` and ``selector`` are mutually exclusive variant modes:

    * Explicit ``params`` should come from declared config. Changing one point
      then invalidates only that point; the edit file still contributes common
      parameters and its fingerprint.
    * A ``selector`` is simple and keeps one authored corner definition in the
      edit file. Its name is config and its values are covered by the edit-file
      fingerprint, so editing any part of that file invalidates every point
      that declares it (coarse invalidation).
    * Caller-supplied ``declarations`` may replace the entire ``PARAM_SETS``
      definition and then be combined with ``selector``. The definitions must
      themselves be declared config; only that config carries their values in
      identity. For fine-grained invalidation, give each invocation a one-item
      replacement containing its own complete set definition. A local or
      module-constant mapping outside config is invisible to reuse and must not
      be used.

    An embedding call always resolves one variant. It never expands a matrix or
    several sets; use :func:`variants` while authoring invocations, or let the
    CLI loop. ``requires`` binds absolute paths by name. Unknown names and
    requirements with neither a caller binding nor a default fail loudly.
    """

    if isinstance(editfile, EditFile):
        if declarations is not None:
            raise EditError("declarations must be supplied when read() creates the EditFile")
        authored = editfile
    else:
        authored = read(editfile, declarations=declarations)

    if params is not None and selector is not None:
        raise EditError("use either explicit params or a selector, not both")
    if params is not None:
        if not isinstance(params, Mapping):
            raise EditError("explicit params must be a mapping")
        resolved_params = authored.common_params | dict(params)
    elif selector is not None:
        if authored.param_matrix:
            raise EditError(
                "a selector plus PARAM_MATRIX describes multiple variants; "
                "expand variants first and pass one point as explicit params"
            )
        resolved_params = dict(_select_param_set(authored.param_sets, selector).params)
    else:
        named = [item.name for item in authored.param_sets if item.name is not None]
        if named:
            raise EditError("named parameter sets require a selector or explicit params")
        if authored.param_matrix:
            raise EditError("PARAM_MATRIX requires explicit params for an embedded render")
        resolved_params = dict(authored.param_sets[0].params)

    resolved_requires = _resolve_requirements(authored, requires or {}, resolved_params)
    context = AuthoringContext(
        requires=resolved_requires,
        params=resolved_params,
        declarations=authored.declarations,
    )
    raw_edits = authored.edit_factory(context)
    if not isinstance(raw_edits, Iterable):
        raise EditError(f"{authored.path} edits_for(ctx) must return an iterable of edit specs")
    built = tuple(raw_edits)
    return RenderPlan(
        editfile_path=authored.path,
        requires=resolved_requires,
        params=resolved_params,
        copy_ignore=authored.copy_ignore,
        edits=_validate_edits(authored.path, built),
        selector=selector,
    )


def materialize(
    plan: RenderPlan,
    output_dir: str | os.PathLike[str],
    *,
    label: str | None = None,
) -> None:
    """Copy the declared base and apply one resolved plan to a new directory.

    The complete edit tuple already exists on ``plan`` before this function
    writes anything. Existing output directories are refused.
    """

    output = Path(output_dir).resolve()
    if output.exists():
        raise EditError(f"output directory already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    copy_base_tree(plan.base_dir, output, list(plan.copy_ignore))
    for index, edit in enumerate(plan.edits, start=1):
        try:
            apply_edit(
                output,
                edit,
                plan.params,
                plan.editfile_dir,
                plan.editfile_path,
                plan.requires,
            )
        except EditError as exc:
            raise EditError(format_edit_failure(plan.editfile_path, index, edit, str(exc))) from exc
    if label:
        print(f"rendered {label}: {output}")
    else:
        print(f"rendered {output}")


def _load_requirements(
    editfile_path: Path,
    raw: object,
) -> dict[str, str | os.PathLike[str] | None]:
    if not isinstance(raw, dict):
        raise EditError(f"{editfile_path} REQUIRES must be a dict")
    result: dict[str, str | os.PathLike[str] | None] = {}
    for name, default in raw.items():
        if not isinstance(name, str) or not PARAM_SET_NAME_RE.match(name):
            raise EditError(f"{editfile_path} REQUIRES name must be a valid identifier: {name!r}")
        if default is not None and not isinstance(default, (str, os.PathLike)):
            raise EditError(f"{editfile_path} REQUIRES entry {name} default must be a path or None")
        result[name] = default
    if "base" not in result:
        raise EditError(f"{editfile_path} REQUIRES must declare the base requirement")
    return result


def _load_common_params(editfile_path: Path, raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise EditError(f"{editfile_path} COMMON_PARAMS must be a dict")
    return dict(raw)


def _load_param_sets(
    editfile_path: Path,
    raw: object,
    common_params: dict[str, object],
) -> list[ParamSet]:
    if raw is None:
        return [ParamSet(name=None, params=dict(common_params))]
    if not isinstance(raw, list):
        raise EditError(f"{editfile_path} PARAM_SETS must be a list")
    param_sets: list[ParamSet] = []
    seen_names: set[str] = set()
    allowed = {"name", "description", "targetdir", "params"}
    for index, raw_param_set in enumerate(raw, start=1):
        if not isinstance(raw_param_set, dict):
            raise EditError(f"{editfile_path} PARAM_SETS entry {index} must be a dict")
        unknown = sorted(set(raw_param_set) - allowed)
        if unknown:
            raise EditError(
                f"{editfile_path} PARAM_SETS entry {index} has unsupported field(s): "
                f"{', '.join(unknown)}"
            )
        name = raw_param_set.get("name")
        if not isinstance(name, str) or not PARAM_SET_NAME_RE.match(name):
            raise EditError(f"{editfile_path} PARAM_SETS entry {index} needs a valid identifier name")
        if name in seen_names:
            raise EditError(f"{editfile_path} defines duplicate PARAM_SETS name: {name}")
        seen_names.add(name)
        params = raw_param_set.get("params", {})
        if not isinstance(params, dict):
            raise EditError(f"{editfile_path} PARAM_SETS entry {name} params must be a dict")
        description = raw_param_set.get("description")
        if description is not None and not isinstance(description, str):
            raise EditError(f"{editfile_path} PARAM_SETS entry {name} description must be a string")
        targetdir = raw_param_set.get("targetdir")
        if targetdir is not None and not isinstance(targetdir, str):
            raise EditError(f"{editfile_path} PARAM_SETS entry {name} targetdir must be a string")
        param_sets.append(
            ParamSet(
                name=name,
                description=description,
                targetdir=targetdir,
                params=common_params | params,
            )
        )
    if not param_sets:
        raise EditError(f"{editfile_path} PARAM_SETS must not be empty")
    return param_sets


def _load_param_matrix(editfile_path: Path, raw: object) -> dict[str, list[object]]:
    if not isinstance(raw, dict):
        raise EditError(f"{editfile_path} PARAM_MATRIX must be a dict")
    matrix: dict[str, list[object]] = {}
    for key, values in raw.items():
        if not isinstance(key, str) or not PARAM_SET_NAME_RE.match(key):
            raise EditError(f"{editfile_path} PARAM_MATRIX key must be a valid identifier: {key}")
        if not isinstance(values, list):
            raise EditError(f"{editfile_path} PARAM_MATRIX entry {key} must be a list")
        if not values:
            raise EditError(f"{editfile_path} PARAM_MATRIX entry {key} must not be empty")
        matrix[key] = list(values)
    return matrix


def _load_copy_ignore(editfile_path: Path, raw: object) -> tuple[str, ...]:
    if not isinstance(raw, (list, tuple)):
        raise EditError(f"{editfile_path} COPY_IGNORE must be a list or tuple")
    return tuple(str(item) for item in raw)


def _select_param_set(param_sets: tuple[ParamSet, ...], selector: str) -> ParamSet:
    named = {item.name: item for item in param_sets if item.name is not None}
    selected = named.get(selector)
    if selected is None:
        available = ", ".join(sorted(named)) or "none"
        raise EditError(f"unknown parameter set: {selector}; available: {available}")
    return selected


def _resolve_requirements(
    authored: EditFile,
    bindings: Mapping[str, str | os.PathLike[str]],
    params: dict[str, object],
) -> dict[str, Path]:
    unknown = sorted(set(bindings) - set(authored.requirement_defaults))
    if unknown:
        raise EditError(f"unknown requirement binding(s): {', '.join(unknown)}")
    resolved: dict[str, Path] = {}
    for name, default in authored.requirement_defaults.items():
        if name in bindings:
            path = Path(bindings[name])
            if not path.is_absolute():
                raise EditError(f"caller requirement {name} must be an absolute path: {path}")
            resolved[name] = path.resolve()
        elif default is None:
            raise EditError(f"required input {name} has no default and no caller binding")
        else:
            resolved[name] = resolve_editfile_path(authored.directory, os.fspath(default), params)
    return resolved


def _validate_edits(
    editfile_path: Path,
    raw_edits: tuple[object, ...],
) -> tuple[edits_api.EditSpec, ...]:
    checked: list[edits_api.EditSpec] = []
    for index, raw_edit in enumerate(raw_edits, start=1):
        if isinstance(raw_edit, dict):
            raise EditError(
                f"{editfile_path} edits_for(ctx) item {index} is a raw dictionary; "
                "use sidecar_edits.edits helpers"
            )
        if not edits_api.is_edit_spec(raw_edit):
            raise EditError(
                f"{editfile_path} edits_for(ctx) item {index} must be a sidecar_edits.edits object"
            )
        checked.append(raw_edit)
    return tuple(checked)


def format_text(value: str, params: Mapping[str, object]) -> str:
    """Format text with resolved parameters and report absent keys uniformly."""

    try:
        return value.format_map(params)
    except KeyError as exc:
        raise EditError(f"missing parameter: {exc.args[0]}") from exc


def format_path_text(value: str, params: Mapping[str, object]) -> str:
    return os.path.expandvars(format_text(value, params))


def format_edit_text(
    value: str,
    params: Mapping[str, object],
    *,
    interpolate: bool,
    expand_env: bool,
) -> str:
    """Apply the independently requested edit-authoring substitutions."""
    if interpolate:
        value = format_text(value, params)
    if expand_env:
        value = os.path.expandvars(value)
    return value


def resolve_editfile_path(base_dir: Path, value: str, params: Mapping[str, object]) -> Path:
    path = Path(format_path_text(value, params))
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_copy_ignore(patterns: list[str]) -> list[str]:
    return [
        stripped
        for pattern in patterns
        if (stripped := str(pattern).strip()) and not stripped.startswith("#")
    ]


def matches_copy_ignore(rel_path: str, name: str, is_dir: bool, pattern: str) -> bool:
    dirs_only = pattern.endswith("/")
    clean_pattern = pattern.strip("/")
    if not clean_pattern or (dirs_only and not is_dir):
        return False
    if "/" in clean_pattern:
        return fnmatch.fnmatchcase(rel_path, clean_pattern)
    return fnmatch.fnmatchcase(name, clean_pattern)


def build_copy_ignore(base_dir: Path, patterns: list[str]):
    ignore_patterns = normalize_copy_ignore(patterns)
    if not ignore_patterns:
        return None

    def ignore(current_dir: str, names: list[str]) -> set[str]:
        ignored = set()
        current_path = Path(current_dir)
        for name in names:
            candidate = current_path / name
            rel_path = candidate.relative_to(base_dir).as_posix()
            if any(
                matches_copy_ignore(rel_path, name, candidate.is_dir(), pattern)
                for pattern in ignore_patterns
            ):
                ignored.add(name)
        return ignored

    return ignore


def copy_base_tree(base_dir: Path, output_dir: Path, copy_ignore: list[str]) -> None:
    if not base_dir.is_dir():
        raise EditError(f"base requirement is not a directory: {base_dir}")
    shutil.copytree(base_dir, output_dir, ignore=build_copy_ignore(base_dir, copy_ignore))


def apply_replace_text(
    target: Path,
    old: str,
    new: str,
    allow_no_match: bool,
    description: str,
) -> None:
    content = read_text(target)
    if old not in content:
        if allow_no_match:
            return
        raise EditError(f"{description} failed: replace target not found in {target}")
    write_text(target, content.replace(old, new))


def apply_regex_replace_text(
    target: Path,
    pattern: str,
    repl: str,
    count: int,
    allow_no_match: bool,
    description: str,
) -> None:
    content = read_text(target)
    updated, replacements = re.subn(pattern, repl, content, count=count, flags=re.MULTILINE)
    if replacements == 0:
        if allow_no_match:
            return
        raise EditError(f"{description} failed: regex pattern not found in {target}: {pattern}")
    write_text(target, updated)


def run_external_patch(
    target_dir: Path,
    patch_text: str,
    command: list[str],
    optional: bool,
    description: str,
) -> None:
    try:
        subprocess.run(
            command,
            input=patch_text,
            text=True,
            cwd=target_dir,
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        if optional:
            print(f"skip optional {description}: command not found: {command[0]}")
            return
        raise EditError(f"{description} failed: required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        if optional:
            print(f"skip optional {description}: {details}")
            return
        raise EditError(f"{description} failed: {details}") from exc


def run_command_args(target_dir: Path, command: list[str], optional: bool, description: str) -> None:
    try:
        subprocess.run(command, cwd=target_dir, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        if optional:
            print(f"skip optional {description}: command not found: {command[0]}")
            return
        raise EditError(f"{description} failed: required command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        if optional:
            print(f"skip optional {description}: {details}")
            return
        raise EditError(f"{description} failed: {details}") from exc


def run_extract_subckts(
    target_dir: Path,
    input_path: str,
    output_main: str,
    output_subckts: str,
    include_path: str,
    optional: bool,
    description: str,
) -> None:
    try:
        binary = str(tool_path("extract_subckts"))
    except RuntimeError as exc:
        if optional:
            print(f"skip optional {description}: {exc}")
            return
        raise EditError(f"{description} failed: {exc}") from exc
    run_command_args(
        target_dir,
        [binary, input_path, output_main, output_subckts, include_path],
        optional,
        description,
    )


def apply_patch_text(
    target_dir: Path,
    patch_text: str,
    binary: str | None,
    command: list[str] | None,
    optional: bool,
    description: str,
) -> None:
    if command is None:
        resolved = shutil.which(binary or "apply_patch")
        if resolved is None:
            message = (
                f"apply_patch executable not found for {description}. "
                "Install apply_patch on PATH or set the edit's binary/command."
            )
            if optional:
                print(f"skip optional {description}: {message}")
                return
            raise EditError(message)
        command = [resolved]
    run_external_patch(target_dir, patch_text, command, optional, description)


def apply_copy_file(target_dir: Path, source: Path, dest_name: str, description: str) -> None:
    if not source.is_file():
        raise EditError(f"{description} failed: copy source does not exist: {source}")
    destination = target_dir / dest_name
    ensure_parent(destination)
    shutil.copy2(source, destination)


def apply_rename_file(
    target_dir: Path,
    pattern: str,
    destination: str,
    allow_no_match: bool,
    description: str,
) -> None:
    try:
        expression = re.compile(pattern)
    except re.error as exc:
        raise EditError(
            f"{description} failed: invalid rename pattern {pattern!r}: {exc}"
        ) from exc

    matched: list[tuple[str, Path, re.Match[str]]] = []
    for item in sorted(target_dir.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(target_dir).as_posix()
        found = expression.fullmatch(relative)
        if found is not None:
            matched.append((relative, item, found))

    if not matched:
        if allow_no_match:
            return
        raise EditError(
            f"{description} failed: rename pattern matched no file: {pattern}"
        )
    if len(matched) > 1:
        candidates = ", ".join(relative for relative, _, _ in matched)
        raise EditError(
            f"{description} failed: rename pattern {pattern} matched "
            f"{len(matched)} files: {candidates}"
        )

    relative, source, found = matched[0]
    try:
        expanded = found.expand(destination)
    except (re.error, IndexError) as exc:
        raise EditError(
            f"{description} failed: invalid rename destination {destination!r}: {exc}"
        ) from exc

    target = target_dir / expanded
    resolved = target.resolve()
    try:
        resolved.relative_to(target_dir.resolve())
    except ValueError:
        raise EditError(
            f"{description} failed: rename destination leaves the run directory: {expanded}"
        ) from None
    if resolved == source.resolve():
        raise EditError(
            f"{description} failed: rename destination is the source file: {relative}"
        )
    if target.exists():
        raise EditError(
            f"{description} failed: rename destination already exists: {expanded}"
        )
    ensure_parent(target)
    source.rename(target)


def apply_write_file(target_dir: Path, path: str, content: str) -> None:
    destination = target_dir / path
    ensure_parent(destination)
    write_text(destination, content)


def apply_append_to_file(target_dir: Path, path: str, content: str, description: str) -> None:
    destination = target_dir / path
    if not destination.is_file():
        raise EditError(f"{description} failed: target file does not exist: {destination}")
    with destination.open("a", encoding="utf-8") as file:
        file.write(content)


def apply_insert_series_source_at_instance_net(
    target: Path,
    instance: str,
    net: str,
    internal_net: str,
    source_line: str,
    description: str,
) -> None:
    content = read_text(target)
    updated = insert_series_source_at_instance_net_text(
        content, instance, net, internal_net, source_line, target, description
    )
    write_text(target, updated)


def insert_series_source_at_instance_net_text(
    content: str,
    instance: str,
    net: str,
    internal_net: str,
    source_line: str,
    target: Path,
    description: str,
) -> str:
    matches = find_instance_statements(content, instance)
    if not matches:
        raise EditError(f"{description} failed: instance not found in {target}: {instance}")
    if len(matches) > 1:
        raise EditError(f"{description} failed: instance is ambiguous in {target}: {instance}")
    statement = matches[0]
    if any(marker in statement.text for marker in ("$", ";", "*")):
        raise EditError(
            f"{description} failed: comments are not supported on instance line: {instance}"
        )
    rewritten = replace_unique_net_token(
        statement.text, instance, net, internal_net, target, description
    )
    source = source_line if source_line.endswith("\n") else f"{source_line}\n"
    return content[: statement.start] + source + rewritten + content[statement.end :]


def find_instance_statements(content: str, instance: str) -> list[LogicalStatement]:
    candidates = accepted_instance_names(instance)
    return [
        statement
        for statement in iter_logical_statements(content)
        if first_token_lower(statement.text) in candidates
    ]


def accepted_instance_names(instance: str) -> set[str]:
    lowered = instance.lower()
    names = {lowered}
    if len(lowered) > 1 and lowered.startswith("x"):
        names.add(f"x{lowered[1]}{lowered[1:]}")
    return names


def iter_logical_statements(content: str) -> list[LogicalStatement]:
    lines = content.splitlines(keepends=True)
    statements: list[LogicalStatement] = []
    offset = 0
    index = 0
    while index < len(lines):
        start = offset
        parts = [lines[index]]
        offset += len(lines[index])
        index += 1
        while index < len(lines) and lines[index].lstrip().startswith("+"):
            parts.append(lines[index])
            offset += len(lines[index])
            index += 1
        statements.append(LogicalStatement(start=start, end=offset, text="".join(parts)))
    return statements


def first_token_lower(text: str) -> str | None:
    match = re.match(r"\s*(\S+)", text)
    return None if match is None else match.group(1).lower()


def replace_unique_net_token(
    text: str,
    instance: str,
    net: str,
    internal_net: str,
    target: Path,
    description: str,
) -> str:
    first = re.match(r"\s*\S+", text)
    if first is None:
        raise EditError(f"{description} failed: malformed instance text in {target}: {instance}")
    pattern = re.compile(r"(?<!\S)" + re.escape(net) + r"(?!\S)")
    matches = [match for match in pattern.finditer(text) if match.start() >= first.end()]
    if not matches:
        raise EditError(
            f"{description} failed: net not found on instance {instance} in {target}: {net}"
        )
    if len(matches) > 1:
        raise EditError(
            f"{description} failed: net appears more than once on instance {instance}: {net}"
        )
    match = matches[0]
    return text[: match.start()] + internal_net + text[match.end() :]


def apply_edit(
    target_dir: Path,
    edit: edits_api.EditSpec,
    params: dict[str, object],
    editfile_dir: Path,
    editfile_path: Path | None = None,
    requires: dict[str, Path] | None = None,
) -> None:
    if not edits_api.is_edit_spec(edit):
        raise EditError("edit must be a sidecar_edits.edits object")
    edit.apply(
        RenderContext(
            target_dir=target_dir,
            editfile_dir=editfile_dir,
            editfile_path=editfile_path or editfile_dir / "<unknown>",
            params=params,
            requires=requires or {},
        )
    )


def format_edit_failure(
    editfile_path: Path,
    index: int,
    edit: edits_api.EditSpec,
    reason: str,
) -> str:
    label = f'edits_for(ctx)[{index}] {edit.op}'
    if edit.description:
        label += f' "{edit.description}"'
    lines = [f"{label} failed"]
    if edit.source_stack:
        first, *rest = edit.source_stack[:3]
        lines.append(f"created at {first.format(editfile_path)}")
        for frame in rest:
            lines.append(f"called from {frame.format(editfile_path)}")
    lines.append(f"reason: {reason}")
    return "\n".join(lines)


def path_slug(value: object) -> str:
    text = str(value).strip()
    if text.startswith("-"):
        text = "m" + text[1:]
    text = text.replace(".", "p")
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "value"


def expand_param_matrix(param_matrix: Mapping[str, list[object]]) -> list[MatrixCase]:
    """Expand explicit matrix axes into stable parameter/suffix cases."""

    if not param_matrix:
        return [MatrixCase(suffix=None, params={})]
    keys = list(param_matrix)
    cases = []
    for values in itertools.product(*(param_matrix[key] for key in keys)):
        params = dict(zip(keys, values))
        suffix = "_".join(
            f"{path_slug(key)}_{path_slug(value)}" for key, value in params.items()
        )
        cases.append(MatrixCase(suffix=suffix, params=params))
    return cases


def _select_cli_variants(
    expanded: tuple[Variant, ...],
    run_names: list[str] | None,
    all_runs: bool,
) -> tuple[Variant, ...]:
    selectors = {item.selector for item in expanded if item.selector is not None}
    if run_names and all_runs:
        raise EditError("use either --run or --all, not both")
    if not selectors:
        if run_names:
            raise EditError("edit file does not define named parameter sets")
        return expanded
    if not run_names:
        return expanded
    missing = [name for name in run_names if name not in selectors]
    if missing:
        raise EditError(
            f"unknown parameter set(s): {', '.join(missing)}; "
            f"available: {', '.join(sorted(selectors))}"
        )
    return tuple(item for item in expanded if item.selector in run_names)


def _base_output_dir(output_base: Path, variant: Variant) -> Path:
    if variant.selector is None:
        return output_base
    if variant.targetdir:
        target = Path(format_path_text(variant.targetdir, variant.params))
        return target if target.is_absolute() else (output_base.parent / target).resolve()
    return output_base.parent / f"{output_base.name}_{variant.selector}"


def _output_dir(output_base: Path, variant: Variant) -> Path:
    base = _base_output_dir(output_base, variant)
    return base if variant.matrix_suffix is None else base / variant.matrix_suffix


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse ``sidecar-render`` command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Resolve an edit file and materialize one or more run directories."
    )
    parser.add_argument("editfile", type=Path, help="Path to the edit file, typically edits.py")
    parser.add_argument("output", type=Path, help="Output run directory or named-run base path")
    parser.add_argument(
        "--run",
        action="append",
        dest="run_names",
        help="Named parameter set to render. Repeat to select several sets.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Render all named sets (already the default).",
    )
    return parser.parse_args(argv)


def main() -> int:
    """Run the public CLI using the same read/resolve/materialize path as Python clients."""

    try:
        args = parse_args()
        authored = read(args.editfile)
        output_base = Path(os.path.expandvars(str(args.output))).resolve()
        for variant in _select_cli_variants(variants(authored), args.run_names, args.all):
            plan = resolve(authored, params=variant.params)
            materialize(plan, _output_dir(output_base, variant), label=variant.name)
        return 0
    except EditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
