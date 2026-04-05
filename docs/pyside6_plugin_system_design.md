# PySide6 Music Player Plugin System Design

## Overview
This document defines a production-ready plugin system for a PySide6-based music player.

---

## Architecture

```
player/
├── core/
│   ├── plugin_manager.py
│   ├── plugin_base.py
│   ├── events.py
│   └── context.py
├── plugins/
├── ui/
└── main.py
```

---

## Core Components

### PluginBase
```python
class PluginBase:
    name = "Unnamed Plugin"
    version = "0.0.1"

    def __init__(self, context):
        self.context = context

    def on_load(self):
        pass

    def on_unload(self):
        pass
```

---

### EventBus
```python
class EventBus:
    def __init__(self):
        self._listeners = {}

    def subscribe(self, event, callback):
        self._listeners.setdefault(event, []).append(callback)

    def emit(self, event, *args, **kwargs):
        for cb in self._listeners.get(event, []):
            cb(*args, **kwargs)
```

---

### Context
```python
class AppContext:
    def __init__(self, player, ui, event_bus):
        self.player = player
        self.ui = ui
        self.event_bus = event_bus
```

---

### PluginManager
```python
import importlib.util
import os
import json

class PluginManager:
    def __init__(self, context, plugin_dir="plugins"):
        self.context = context
        self.plugin_dir = plugin_dir
        self.plugins = []

    def load_plugins(self):
        for folder in os.listdir(self.plugin_dir):
            path = os.path.join(self.plugin_dir, folder)

            manifest_path = os.path.join(path, "plugin.json")
            main_path = os.path.join(path, "main.py")

            if not os.path.exists(manifest_path):
                continue

            with open(manifest_path) as f:
                manifest = json.load(f)

            spec = importlib.util.spec_from_file_location(
                manifest["name"], main_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin_class = getattr(module, "Plugin")
            plugin = plugin_class(self.context)

            plugin.on_load()
            self.plugins.append(plugin)
```

---

## Plugin Structure

```
plugins/example_plugin/
├── plugin.json
└── main.py
```

### plugin.json
```json
{
  "name": "example_plugin",
  "version": "1.0.0",
  "main": "main.py"
}
```

### main.py
```python
from core.plugin_base import PluginBase

class Plugin(PluginBase):
    def on_load(self):
        print("Plugin loaded")
```

---

## UI Extension

```python
self.context.ui.add_tab(widget, "Tab Name")
self.context.ui.add_menu_action("Tools", "Action", callback)
```

---

## Hot Reload

```python
def reload_plugins(self):
    for p in self.plugins:
        p.on_unload()
    self.plugins.clear()
    self.load_plugins()
```

---

## Advanced Features

- Plugin marketplace
- Dependency management
- Permission system
- Multi-process sandbox plugins

---

## Minimal Demo

```python
event_bus.emit("track_changed", {"title": "Song A"})
```

---

## Conclusion

Key principles:
- Dynamic loading
- Clear interfaces
- Event-driven
- Context isolation
