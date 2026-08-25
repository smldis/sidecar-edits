from sidecar_edits import edits


REQUIRES = {
    "base": "base",
    "model_override": "assets/model_override.scs",
}

COMMON_PARAMS = {
    "netlist_path": "/work/netlists/rc_filter_corner_tt.scs",
}

# Other supported operations: regex_replace, patch, and apply_patch.

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
        ),
    ]
