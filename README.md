# Harmony

[简体中文](README-cn.md)

Harmony is a desktop music player built with Python and PySide6. It combines a local music library, cloud-drive playback, a plugin-based online music stack, and a layered architecture designed for long-term maintenance.

## Highlights

- Local library management with folder scanning, metadata extraction, embedded-cover support, SQLite FTS5 search, and album/artist/genre aggregation
- Playback queue persistence, multiple play modes, mini player, now-playing window, sleep timer, equalizer UI, favorites, history, recently added, and most-played views
- Cloud drive playback for Quark and Baidu, including QR login, folder browsing, download/cache handling, and share-link search
- Plugin system for online music providers, lyrics sources, cover sources, sidebar entries, and settings tabs
- Built-in lyrics and cover providers, plus a built-in QQ Music plugin for online browsing, search, login, queue actions, lyrics, and cover data
- Optional AI metadata completion through OpenAI-compatible APIs and optional AcoustID fingerprint lookup
- Chinese/English UI, theme system, bundled fonts, and platform-specific media-key integration where runtime support exists

## Built-in Plugins

Built-in plugins are loaded from [`plugins/builtin`](plugins/builtin). External plugins can be installed from zip files or URLs in `Settings -> Plugins`.

| Plugin | Capability |
| --- | --- |
| `qqmusic` | Online music provider, sidebar entry, settings tab, lyrics source, cover source |
| `lrclib` | Lyrics source |
| `netease_lyrics` | Lyrics source |
| `kuogo_lyrics` | Lyrics source |
| `netease_cover` | Cover source |
| `itunes_cover` | Cover source |
| `last_fm_cover` | Cover source |

## Requirements

- Python 3.11+
- `uv`
- Windows, Linux, or macOS
- `libmpv` runtime if you want the `mpv` backend

`mpv` runtime notes:

- Linux (Debian/Ubuntu): `sudo apt-get install libmpv-dev`
- macOS (Homebrew): `brew install mpv`
- Windows: install `mpv` or make sure `mpv-2.dll` is available in `PATH`

## Quick Start

```bash
git clone https://github.com/power721/Harmony.git
cd Harmony

# Runtime dependencies
uv sync

# Optional: development tools such as pytest, pytest-qt, ruff, pyright
uv sync --extra dev --group dev

# Optional: download bundled fonts for development
./download_fonts.sh

# Launch the app
uv run python main.py
```

See [`docs/font-bundling.md`](docs/font-bundling.md) for font details.

## Everyday Usage

- Click `Add Music` to scan local folders and build the library
- Open `Cloud Drive` to log into Quark or Baidu and browse remote files
- Open `Settings -> Plugins` to enable, disable, or install plugins
- Open `Settings -> Playback` to switch between `mpv` and `Qt Multimedia`
- Open `Settings -> AI` or `Settings -> AcoustID` to configure optional metadata services

## Development

Useful commands:

```bash
# Run the application
uv run python main.py

# Run the full test suite
uv run pytest tests/

# Faster UI-focused checks
uv run pytest tests/test_ui/ -m "not slow"

# Lint
uv run ruff check .

# Build for the current platform
./build.sh

# Explicit cross-platform build script
uv run python build.py linux
uv run python build.py macos
uv run python build.py windows

# Linux release/AppImage pipeline
./release.sh
```

Pytest markers defined in [`pytest.ini`](pytest.ini):

- `unit`
- `integration`
- `slow`

## Architecture

Harmony follows a layered architecture:

```text
UI -> Services -> Repositories -> Infrastructure
      \-------> Domain <-------/
```

Top-level layout:

```text
app/            Application bootstrap and dependency wiring
domain/         Pure domain models
repositories/   SQLite-backed persistence adapters
services/       Library, playback, cloud, download, lyrics, metadata, AI
infrastructure/ Audio backends, database, cache, network, fonts, security
system/         Config, event bus, theme, i18n, hotkeys, plugin host
ui/             Windows, dialogs, widgets, views, controllers, workers
plugins/        Built-in plugin implementations
packages/       Local plugin SDK package (`harmony-plugin-api`)
tests/          Pytest suites by layer
docs/           Design notes, bug reports, implementation docs
data/           Development-time writable app data
```

## Runtime Notes

- In development, writable data lives under [`data/`](data). In bundled builds, Harmony uses the platform app-data directory.
- The development database is `Harmony.db` in the project root.
- Built-in fonts are loaded from [`fonts/`](fonts); if they are missing, Harmony falls back to system fonts.
- Linux media-key support uses MPRIS when QtDBus is available. Windows can use `pynput`. macOS currently falls back to focused shortcuts.

## Screenshots

Sample UI captures are available in [`screenshots/`](screenshots).
