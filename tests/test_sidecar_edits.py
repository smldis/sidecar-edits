from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
BASIC_EDITS = REPO_ROOT / "examples" / "basic" / "edits.py"
APPLY_PATCH_EDITS = REPO_ROOT / "examples" / "apply_patch" / "edits.py"
PARAM_MATRIX_EDITS = REPO_ROOT / "examples" / "param_matrix" / "edits.py"
PWL_EXCEL_EDITS = REPO_ROOT / "examples" / "pwl_excel" / "edits.py"

sys.path.insert(0, str(REPO_ROOT / "src"))

import sidecar_edits  # noqa: E402
from sidecar_edits.render import (  # noqa: E402
    EditError,
    copy_base_tree,
    materialize,
    read,
    resolve,
    variants,
)


def build_package(tmp_path: Path) -> Path:
    build_lib = tmp_path / "build_lib"
    subprocess.run(
        [sys.executable, "setup.py", "build_py", "--build-lib", str(build_lib)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return build_lib


def run_cli(editfile: Path, output: Path, *args: str, env: dict[str, str] | None = None):
    command_env = os.environ.copy()
    command_env["PYTHONPATH"] = str(REPO_ROOT / "src")
    if env:
        command_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "sidecar_edits.render", str(editfile), str(output), *args],
        cwd=REPO_ROOT,
        env=command_env,
        capture_output=True,
        text=True,
    )


def write_editfile(tmp_path: Path, body: str, *, base_text: str = "seed\n") -> Path:
    base = tmp_path / "base"
    base.mkdir(exist_ok=True)
    (base / "input.txt").write_text(base_text, encoding="utf-8")
    path = tmp_path / "edits.py"
    path.write_text(body, encoding="utf-8")
    return path


def write_fake_apply_patch(bin_dir: Path) -> Path:
    binary = bin_dir / "apply_patch"
    binary.write_text(
        f"""#!{sys.executable}
from pathlib import Path
import sys

patch = sys.stdin.read()
if "*** Add File: APPLY_PATCH_PROOF.txt" not in patch:
    raise SystemExit(2)
Path("APPLY_PATCH_PROOF.txt").write_text("run_label=tt_1v2_27c\\n", encoding="utf-8")
""",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def test_tool_path_builds_extract_subckts_for_editable_source_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = tmp_path / "sidecar_edits"
    (package_root / "native").mkdir(parents=True)
    (package_root / "native" / "extract_subckts.c").write_text(
        "int main(void) { return 0; }\n", encoding="utf-8"
    )
    captured = {}

    def fake_files(package: str) -> Path:
        assert package == "sidecar_edits"
        return package_root

    def fake_run(command: list[str], check: bool) -> None:
        captured["command"] = command
        captured["check"] = check
        Path(command[command.index("-o") + 1]).write_text("binary\n", encoding="utf-8")

    monkeypatch.setattr(sidecar_edits, "files", fake_files)
    monkeypatch.setattr(sidecar_edits.subprocess, "run", fake_run)

    path = sidecar_edits.tool_path("extract_subckts")

    assert path == package_root / "bin" / "extract_subckts"
    assert path.read_text(encoding="utf-8") == "binary\n"
    assert captured["check"] is True


def test_tool_path_reports_missing_native_source_for_unbuilt_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = tmp_path / "sidecar_edits"
    package_root.mkdir()
    monkeypatch.setattr(sidecar_edits, "files", lambda package: package_root)
    with pytest.raises(RuntimeError, match="Install a built wheel"):
        sidecar_edits.tool_path("extract_subckts")


def test_basic_example_render_applies_declared_edits_from_built_package(tmp_path: Path) -> None:
    build_lib = build_package(tmp_path)
    output = tmp_path / "example_run"
    result = run_cli(BASIC_EDITS, output, env={"PYTHONPATH": str(build_lib)})
    assert result.returncode == 0, result.stderr
    assert (output / "include" / "model_override.scs").read_text(encoding="utf-8") == (
        "simulator lang=spectre\nparameters gain_trim=1.05\n"
    )
    assert 'include "/work/netlists/rc_filter_corner_tt.scs"' in (
        output / "input_main.scs"
    ).read_text(encoding="utf-8")
    assert ".SUBCKT rc_filter in out" in (output / "subckts.inc").read_text(encoding="utf-8")


def test_apply_patch_example_uses_installed_apply_patch_binary(tmp_path: Path) -> None:
    output_base = tmp_path / "apply_patch_run"
    output = tmp_path / "apply_patch_run_tt_1v2"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_apply_patch(bin_dir)
    result = run_cli(
        APPLY_PATCH_EDITS,
        output_base,
        env={"PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"},
    )
    assert result.returncode == 0, result.stderr
    assert (output / "APPLY_PATCH_PROOF.txt").read_text(encoding="utf-8") == (
        "run_label=tt_1v2_27c\n"
    )
    assert "parameters vdd=1.20 temp=27" in (output / "input_main.scs").read_text(
        encoding="utf-8"
    )
    assert not (output / "psf").exists()
    assert not (output / "scratch.tmp").exists()


def test_param_matrix_example_renders_named_matrix_dirs(tmp_path: Path) -> None:
    output = tmp_path / "matrix_run"
    result = run_cli(PARAM_MATRIX_EDITS, output)
    assert result.returncode == 0, result.stderr
    tt = tmp_path / "matrix_run_tt" / "vdd_0p90_temp_c_m40" / "input.scs"
    ss = tmp_path / "custom_ss_sweep" / "vdd_1p20_temp_c_125" / "input.scs"
    assert "parameters corner=tt vdd=0.90 temp=-40" in tt.read_text(encoding="utf-8")
    assert "parameters corner=ss vdd=1.20 temp=125" in ss.read_text(encoding="utf-8")


def test_generator_factory_materializes_conditional_edit_by_variant(tmp_path: Path) -> None:
    common = {"vdd": "1.20", "temp_c": 27}
    tt_plan = resolve(
        PARAM_MATRIX_EDITS,
        params={
            **common,
            "corner": "tt",
            "netlist_path": "/work/netlists/amp_tt.scs",
        },
    )
    ss_plan = resolve(
        PARAM_MATRIX_EDITS,
        params={
            **common,
            "corner": "ss",
            "netlist_path": "/work/netlists/amp_ss.scs",
        },
    )

    conditional_description = "mark typical-corner preparation"
    assert conditional_description in [edit.description for edit in tt_plan.edits]
    assert conditional_description not in [edit.description for edit in ss_plan.edits]

    tt_output = tmp_path / "tt"
    ss_output = tmp_path / "ss"
    materialize(tt_plan, tt_output)
    materialize(ss_plan, ss_output)
    marker = "* typical-corner reference configuration\n"
    assert marker in (tt_output / "input.scs").read_text(encoding="utf-8")
    assert marker not in (ss_output / "input.scs").read_text(encoding="utf-8")


def test_pwl_excel_example_generates_include_from_workbook(tmp_path: Path) -> None:
    output = tmp_path / "pwl_excel_run"
    result = run_cli(PWL_EXCEL_EDITS, output)
    assert result.returncode == 0, result.stderr
    assert (output / "generated" / "pwl_sources.inc").read_text(encoding="utf-8") == (
        "Vvin vin 0 PWL(0 0 1n 0.2 5n 1.2)\n"
        "Vvclk vclk 0 PWL(0 0 1n 1.2 2n 0)\n"
        "Vireset ireset 0 PWL(2n 1m 5n 0)\n"
    )


def test_read_does_not_build_edits_or_read_excel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sidecar_edits import pwl

    monkeypatch.setattr(
        pwl,
        "waveforms_from_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("workbook read at import")),
    )
    authored = read(PWL_EXCEL_EDITS)
    assert authored.requirement_defaults["startup_table"] == "waveforms/startup.xlsx"


def test_resolve_builds_complete_plan_before_materialization(tmp_path: Path) -> None:
    plan = resolve(BASIC_EDITS)
    assert len(plan.edits) == 3
    assert plan.base_dir == BASIC_EDITS.parent / "base"
    assert not (tmp_path / "run").exists()
    materialize(plan, tmp_path / "run")
    assert (tmp_path / "run" / "input_main.scs").is_file()


def test_requirements_use_defaults_and_caller_absolute_bindings(tmp_path: Path) -> None:
    alternate = tmp_path / "alternate"
    alternate.mkdir()
    (alternate / "input.txt").write_text("seed\n", encoding="utf-8")
    editfile = write_editfile(
        tmp_path,
        '''
from sidecar_edits import edits
REQUIRES = {"base": "base"}
def edits_for(ctx):
    return [edits.replace(path="input.txt", old="seed", new="bound")]
''',
    )
    plan = resolve(editfile, requires={"base": alternate.resolve()})
    assert plan.base_dir == alternate.resolve()


def test_unknown_requirement_binding_fails_loudly(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        'REQUIRES = {"base": "base"}\ndef edits_for(ctx): return []\n',
    )
    with pytest.raises(EditError, match="unknown requirement binding.*typo"):
        resolve(editfile, requires={"typo": tmp_path.resolve()})


def test_requirement_without_default_or_binding_fails_loudly(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        'REQUIRES = {"base": "base", "table": None}\ndef edits_for(ctx): return []\n',
    )
    with pytest.raises(EditError, match="table has no default and no caller binding"):
        resolve(editfile)


def test_caller_requirement_must_be_absolute(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        'REQUIRES = {"base": "base"}\ndef edits_for(ctx): return []\n',
    )
    with pytest.raises(EditError, match="must be an absolute path"):
        resolve(editfile, requires={"base": Path("relative")})


def test_caller_declarations_replace_whole_values(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        '''
REQUIRES = {"base": "base"}
COMMON_PARAMS = {"from_file": 1, "shared": "file"}
PARAM_SETS = [{"name": "file_set", "params": {"corner": "file"}}]
PARAM_MATRIX = {"temp": [27, 125]}
def edits_for(ctx): return []
''',
    )
    supplied = {
        "COMMON_PARAMS": {"shared": "caller"},
        "PARAM_SETS": [{"name": "caller_set", "params": {"corner": "caller"}}],
        "PARAM_MATRIX": {},
    }
    authored = read(editfile, declarations=supplied)
    assert authored.common_params == {"shared": "caller"}
    assert [item.name for item in authored.param_sets] == ["caller_set"]
    assert authored.param_matrix == {}
    plan = resolve(authored, selector="caller_set")
    assert plan.params == {"shared": "caller", "corner": "caller"}


def test_supplied_requirements_declaration_replaces_file_definition(tmp_path: Path) -> None:
    alternate = tmp_path / "alternate"
    alternate.mkdir()
    editfile = write_editfile(
        tmp_path,
        'REQUIRES = {"base": "base", "unused": "missing"}\ndef edits_for(ctx): return []\n',
    )
    plan = resolve(
        editfile,
        declarations={"REQUIRES": {"base": None}},
        requires={"base": alternate.resolve()},
    )
    assert plan.requires == {"base": alternate.resolve()}


def test_supplied_set_definitions_and_selector_are_orthogonal(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        '''
REQUIRES = {"base": "base"}
PARAM_SETS = [{"name": "file", "params": {"corner": "file"}}]
def edits_for(ctx): return []
''',
    )
    plan = resolve(
        editfile,
        declarations={
            "PARAM_SETS": [
                {"name": "ss", "params": {"corner": "ss"}},
            ]
        },
        selector="ss",
    )
    assert plan.selector == "ss"
    assert plan.params == {"corner": "ss"}


def test_explicit_params_ignore_set_selection_but_merge_common(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        '''
REQUIRES = {"base": "base"}
COMMON_PARAMS = {"simulator": "ngspice", "corner": "common"}
PARAM_SETS = [{"name": "tt", "params": {"corner": "tt"}}]
def edits_for(ctx): return []
''',
    )
    plan = resolve(editfile, params={"corner": "explicit", "temp": 27})
    assert plan.params == {"simulator": "ngspice", "corner": "explicit", "temp": 27}


def test_variants_are_data_and_can_resolve_caller_definitions_without_file_io() -> None:
    declarations = {
        "COMMON_PARAMS": {"simulator": "ngspice"},
        "PARAM_SETS": [
            {"name": "tt", "params": {"corner": "tt"}},
            {"name": "ss", "params": {"corner": "ss"}},
        ],
        "PARAM_MATRIX": {"temp": [-40, 125]},
    }
    expanded = variants(declarations)
    assert [item.name for item in expanded] == [
        "tt__temp_m40",
        "tt__temp_125",
        "ss__temp_m40",
        "ss__temp_125",
    ]
    assert expanded[-1].params == {"simulator": "ngspice", "corner": "ss", "temp": 125}


def test_embedding_selector_refuses_matrix_fanout(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        '''
REQUIRES = {"base": "base"}
PARAM_SETS = [{"name": "tt", "params": {"corner": "tt"}}]
PARAM_MATRIX = {"temp": [27, 125]}
def edits_for(ctx): return []
''',
    )
    with pytest.raises(EditError, match="describes multiple variants"):
        resolve(editfile, selector="tt")


def test_cli_run_selector_filters_sets_before_matrix_expansion(tmp_path: Path) -> None:
    result = run_cli(PARAM_MATRIX_EDITS, tmp_path / "run", "--run", "ss")
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "run_tt").exists()
    assert (tmp_path / "custom_ss_sweep" / "vdd_0p90_temp_c_27" / "input.scs").is_file()


def test_cli_unknown_selector_fails_loudly(tmp_path: Path) -> None:
    result = run_cli(PARAM_MATRIX_EDITS, tmp_path / "run", "--run", "missing")
    assert result.returncode == 2
    assert "unknown parameter set" in result.stderr


def test_param_set_file_fields_are_rejected_as_undeclared_artifact_locators(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        '''
REQUIRES = {"base": "base"}
PARAM_SETS = [{"name": "tt", "params_file": "params.json"}]
def edits_for(ctx): return []
''',
    )
    with pytest.raises(EditError, match="unsupported field.*params_file"):
        read(editfile)


def test_removed_authoring_declarations_fail_instead_of_coexisting(tmp_path: Path) -> None:
    old_list_name = "ED" + "ITS"
    editfile = write_editfile(
        tmp_path,
        f'''REQUIRES = {{"base": "base"}}
{old_list_name} = []
def edits_for(ctx): return []
''',
    )
    with pytest.raises(EditError, match="uses removed declaration"):
        read(editfile)


def test_raw_dictionary_result_is_rejected(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        '''
REQUIRES = {"base": "base"}
def edits_for(ctx):
    return [{"op": "replace", "path": "input.txt", "old": "a", "new": "b"}]
''',
    )
    with pytest.raises(EditError, match="raw dictionary"):
        resolve(editfile)


def test_source_trace_points_into_factory_body(tmp_path: Path) -> None:
    editfile = write_editfile(
        tmp_path,
        '''
from sidecar_edits import edits
REQUIRES = {"base": "base"}
def make_edit():
    return edits.replace(path="input.txt", old="missing", new="new")
def edits_for(ctx):
    return [make_edit()]
''',
    )
    plan = resolve(editfile)
    assert plan.edits[0].source_stack[0].function == "make_edit"
    with pytest.raises(EditError, match=r"edits_for\(ctx\)\[1\] replace failed") as caught:
        materialize(plan, tmp_path / "run")
    assert "created at edits.py:5 in make_edit" in str(caught.value)
    assert "called from edits.py:7 in edits_for" in str(caught.value)


def test_materialize_refuses_existing_output(tmp_path: Path) -> None:
    plan = resolve(BASIC_EDITS)
    output = tmp_path / "run"
    output.mkdir()
    with pytest.raises(EditError, match="already exists"):
        materialize(plan, output)


def test_copy_base_tree_ignores_directories_basenames_and_relative_paths(tmp_path: Path) -> None:
    base = tmp_path / "base"
    output = tmp_path / "run"
    (base / "psf").mkdir(parents=True)
    (base / "logs").mkdir()
    (base / "nested").mkdir()
    (base / "input.scs").write_text("netlist\n", encoding="utf-8")
    (base / "psf" / "old.raw").write_text("waveform\n", encoding="utf-8")
    (base / "nested" / "scratch.tmp").write_text("scratch\n", encoding="utf-8")
    (base / "logs" / "run.txt").write_text("log\n", encoding="utf-8")
    copy_base_tree(base, output, ["psf/", "*.tmp", "logs/*.txt"])
    assert (output / "input.scs").is_file()
    assert not (output / "psf").exists()
    assert not (output / "nested" / "scratch.tmp").exists()
    assert not (output / "logs" / "run.txt").exists()
