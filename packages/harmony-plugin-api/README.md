# harmony-plugin-api

Pure plugin SDK for Harmony plugins.

This package only contains stable plugin-facing protocols, models, manifest parsing,
and registry spec types. It does not include Harmony host runtime implementations.

Host-specific theme, dialog, runtime, and bootstrap integrations must be provided by
the Harmony application and injected through `PluginContext`.
