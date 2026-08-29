from sidecar_edits import edits


REQUIRES = {
    "base": "base",
    "model_override": "assets/model_override.scs",
}

COPY_IGNORE = [
    "psf/",
    "*.tmp",
]

COMMON_PARAMS = {
    "simulator_cmd": "spectre",
}

PARAM_SETS = [
    {
        "name": "tt_1v2",
        "description": "typical corner at 1.2 V",
        "params": {
            "netlist_path": "/work/netlists/rc_filter_corner_tt.scs",
            "run_label": "tt_1v2_27c",
            "temp_c": 27,
            "vdd": "1.20",
        },
    },
]

def edits_for(ctx):
    return [
        edits.extract_subckts(
            description="split reusable subcircuits from main netlist",
            input="input.scs",
            output_main="input_main.scs",
            output_subckts="subckts.inc",
        ),
        edits.copy_file(
            path=str(ctx.requires["model_override"]),
            to="include/model_override.scs",
        ),
        edits.replace(
            path="input_main.scs",
            old='include "/seed/netlists/rc_filter.scs"',
            new='include "{netlist_path}"',
            interpolate=True,
        ),
        edits.regex_replace(
            path="input_main.scs",
            pattern=r"parameters vdd=\S+ temp=\S+",
            new="parameters vdd={vdd} temp={temp_c}",
            interpolate=True,
        ),
        edits.replace(
            path="run_sim.sh",
            old="spectre input_main.scs -format psfxl -raw ./psf",
            new="{simulator_cmd} input_main.scs -format psfxl -raw ./psf",
            interpolate=True,
        ),
        edits.patch(
            description="add run label to notes",
            optional=True,
            strip=0,
            patch="""--- notes.txt.orig
+++ notes.txt
@@ -1 +1,2 @@
 base example
+run_label={run_label}
""",
            interpolate=True,
        ),
        edits.apply_patch(
            description="add apply_patch proof file",
            patch="""*** Begin Patch
*** Add File: APPLY_PATCH_PROOF.txt
+run_label={run_label}
*** End Patch
""",
            interpolate=True,
        ),
    ]
