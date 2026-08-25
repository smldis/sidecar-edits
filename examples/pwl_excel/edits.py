from sidecar_edits import edits, pwl


REQUIRES = {
    "base": "base",
    "startup_table": "waveforms/startup.xlsx",
}

def edits_for(ctx):
    waveforms = pwl.waveforms_from_file(
        ctx.requires["startup_table"],
        sheet="startup",
    )
    pwl_source_lines = "\n".join(
        f"V{name} {name} 0 {waveform.render_pwl()}"
        for name, waveform in waveforms.items()
    ) + "\n"
    return [
        edits.write_file(
            path="generated/pwl_sources.inc",
            content=pwl_source_lines,
            description="generate PWL sources from spreadsheet",
        ),
        edits.append_to_file(
            path="input.scs",
            content='include "generated/pwl_sources.inc"\n',
            description="include generated PWL sources",
        ),
    ]
