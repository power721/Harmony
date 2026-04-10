# Plugin Restart Toggle Design

## Goal

Allow plugins that are unsafe to hot enable or hot disable to declare that toggle changes only take effect after an application restart.

## Scope

- Add an optional manifest flag to mark plugins that require restart on enable or disable.
- Keep existing immediate toggle behavior for plugins that do not declare the flag.
- Show a user-facing message after toggling a restart-required plugin.

## Design

### Manifest

Add `requires_restart_on_toggle: bool = False` to the plugin manifest contract. This keeps the default behavior unchanged and lets individual plugins opt into restart-only toggle semantics.

### Plugin Manager

When `set_plugin_enabled()` is called for a restart-required plugin:

- persist the new enabled state
- do not call `_load_plugin_root()`
- do not call `_unload_plugin()`

For all other plugins, keep the current immediate load or unload behavior.

### UI

Expose the restart requirement through `PluginManager.list_plugins()` so the plugin management tab can decide whether to show a restart message.

After a restart-required plugin is toggled, show a modal information dialog telling the user the change will apply after restarting the app.

## Initial Plugin

Set `requires_restart_on_toggle` to `true` for the built-in QQ Music plugin because its UI can remain alive after runtime context teardown, which makes hot disable unsafe.

## Testing

- manifest parsing accepts the new field and defaults it to `False`
- plugin manager persists state without hot load or unload for restart-required plugins
- plugin management tab shows the restart prompt after toggling such a plugin
