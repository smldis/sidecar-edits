from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sidecar_edits import edits, render  # noqa: E402


def _context(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(target_dir=tmp_path, params={"vdd": "1.2", "corner": "tt"})


def test_all_edit_factories_expose_default_false_formatting_flags() -> None:
    factories = (
        edits.extract_subckts,
        edits.copy_file,
        edits.rename_file,
        edits.write_file,
        edits.append_to_file,
        edits.insert_series_source_at_instance_net,
        edits.replace,
        edits.regex_replace,
        edits.run,
        edits.patch,
        edits.apply_patch,
    )

    for factory in factories:
        signature = inspect.signature(factory)
        for name in ("interpolate", "expand_env"):
            parameter = signature.parameters[name]
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
            assert parameter.annotation == "bool"
            assert parameter.default is False


@pytest.mark.parametrize(
    ("interpolate", "expand_env", "expected"),
    [
        (False, False, "{corner}/$SIDECAR_TEST_VAR"),
        (True, False, "tt/$SIDECAR_TEST_VAR"),
        (False, True, "{corner}/expanded"),
        (True, True, "tt/expanded"),
    ],
)
def test_format_edit_text_supports_all_four_flag_combinations(
    monkeypatch: pytest.MonkeyPatch,
    interpolate: bool,
    expand_env: bool,
    expected: str,
) -> None:
    monkeypatch.setenv("SIDECAR_TEST_VAR", "expanded")

    assert render.format_edit_text(
        "{corner}/$SIDECAR_TEST_VAR",
        {"corner": "tt"},
        interpolate=interpolate,
        expand_env=expand_env,
    ) == expected


def test_path_with_parameter_braces_is_literal_by_default(tmp_path: Path) -> None:
    edits.write_file(
        path="{corner}/input.scs",
        content="literal\n",
    ).apply(_context(tmp_path))

    assert (tmp_path / "{corner}" / "input.scs").read_text(encoding="utf-8") == (
        "literal\n"
    )


def test_run_awk_program_reaches_tool_byte_identical_under_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    def capture_command(
        target_dir: Path,
        command: list[str],
        optional: bool,
        description: str,
    ) -> None:
        assert target_dir == tmp_path
        captured.extend(command)

    monkeypatch.setattr(render, "run_command_args", capture_command)

    edits.run(command=["awk", "{print $1}", "input.scs"]).apply(_context(tmp_path))

    assert captured == ["awk", "{print $1}", "input.scs"]


def test_defined_parameter_braces_remain_verbatim_by_default(
    tmp_path: Path,
) -> None:
    default_dir = tmp_path / "default"
    interpolated_dir = tmp_path / "interpolated"
    default_dir.mkdir()
    interpolated_dir.mkdir()
    for target_dir in (default_dir, interpolated_dir):
        (target_dir / "input.scs").write_text("INSERT\n", encoding="utf-8")

    edits.replace(
        path="input.scs",
        old="INSERT",
        new="parameters corner={corner}",
    ).apply(_context(default_dir))
    edits.replace(
        path="input.scs",
        old="INSERT",
        new="parameters corner={corner}",
        interpolate=True,
    ).apply(_context(interpolated_dir))

    assert (default_dir / "input.scs").read_text(encoding="utf-8") == (
        "parameters corner={corner}\n"
    )
    assert (interpolated_dir / "input.scs").read_text(encoding="utf-8") == (
        "parameters corner=tt\n"
    )


@pytest.mark.parametrize(
    ("spec", "apply_name", "payload_indexes", "expected"),
    [
        (
            edits.write_file(path="out.scs", content="value={vdd}", interpolate=True),
            "apply_write_file",
            (2,),
            ("value=1.2",),
        ),
        (
            edits.append_to_file(
                path="out.scs", content="value={vdd}", interpolate=True
            ),
            "apply_append_to_file",
            (2,),
            ("value=1.2",),
        ),
        (
            edits.insert_series_source_at_instance_net(
                path="out.scs",
                instance="X1",
                net="in",
                internal_net="in_internal",
                source_line="V1 {net} {internal_net} {vdd}",
                interpolate=True,
            ),
            "apply_insert_series_source_at_instance_net",
            (4,),
            ("V1 in in_internal 1.2",),
        ),
        (
            edits.replace(
                path="out.scs",
                old="old={vdd}",
                new="new={vdd}",
                interpolate=True,
            ),
            "apply_replace_text",
            (1, 2),
            ("old=1.2", "new=1.2"),
        ),
        (
            edits.regex_replace(
                path="out.scs", pattern="old", new="new={vdd}", interpolate=True
            ),
            "apply_regex_replace_text",
            (2,),
            ("new=1.2",),
        ),
        (
            edits.patch(patch="value={vdd}", interpolate=True),
            "run_external_patch",
            (1,),
            ("value=1.2",),
        ),
        (
            edits.apply_patch(patch="value={vdd}", interpolate=True),
            "apply_patch_text",
            (1,),
            ("value=1.2",),
        ),
    ],
    ids=lambda value: getattr(value, "op", None),
)
def test_text_payloads_interpolate_when_explicitly_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec: edits.EditSpec,
    apply_name: str,
    payload_indexes: tuple[int, ...],
    expected: tuple[str, ...],
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(render, apply_name, lambda *args: captured.extend(args))

    spec.apply(_context(tmp_path))

    assert spec.interpolate is True
    assert tuple(captured[index] for index in payload_indexes) == expected


@pytest.mark.parametrize(
    ("spec", "apply_name", "payload_indexes", "expected"),
    [
        (
            edits.write_file(path="out.scs", content="value={vdd}"),
            "apply_write_file",
            (2,),
            ("value={vdd}",),
        ),
        (
            edits.append_to_file(path="out.scs", content="value={vdd}"),
            "apply_append_to_file",
            (2,),
            ("value={vdd}",),
        ),
        (
            edits.insert_series_source_at_instance_net(
                path="out.scs",
                instance="X1",
                net="in",
                internal_net="in_internal",
                source_line="V1 {net} {internal_net} {vdd}",
            ),
            "apply_insert_series_source_at_instance_net",
            (4,),
            ("V1 {net} {internal_net} {vdd}",),
        ),
        (
            edits.replace(
                path="out.scs",
                old="old={vdd}",
                new="new={vdd}",
            ),
            "apply_replace_text",
            (1, 2),
            ("old={vdd}", "new={vdd}"),
        ),
        (
            edits.regex_replace(
                path="out.scs", pattern="old", new="new={vdd}"
            ),
            "apply_regex_replace_text",
            (2,),
            ("new={vdd}",),
        ),
        (
            edits.patch(patch="value={vdd}"),
            "run_external_patch",
            (1,),
            ("value={vdd}",),
        ),
        (
            edits.apply_patch(patch="value={vdd}"),
            "apply_patch_text",
            (1,),
            ("value={vdd}",),
        ),
    ],
    ids=lambda value: getattr(value, "op", None),
)
def test_text_payloads_are_verbatim_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec: edits.EditSpec,
    apply_name: str,
    payload_indexes: tuple[int, ...],
    expected: tuple[str, ...],
) -> None:
    captured: list[object] = []
    monkeypatch.setattr(render, apply_name, lambda *args: captured.extend(args))

    spec.apply(_context(tmp_path))

    assert spec.interpolate is False
    assert tuple(captured[index] for index in payload_indexes) == expected
