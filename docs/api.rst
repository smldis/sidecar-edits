API Reference
=============

Edits API
---------

.. automodule:: sidecar_edits.edits
   :members: extract_subckts, copy_file, rename_file, write_file, append_to_file, insert_series_source_at_instance_net, replace, regex_replace, patch, apply_patch
   :undoc-members:

Authoring and Rendering API
---------------------------

.. automodule:: sidecar_edits.render
   :members: EditError, ParamSet, Variant, EditFile, AuthoringContext, RenderPlan, read, variants, resolve, materialize, expand_param_matrix

PWL Table Helpers
-----------------

.. automodule:: sidecar_edits.pwl
   :members: PwlTableError, PwlPoint, PwlWaveform, waveforms_from_text, waveforms_from_file
   :undoc-members:
