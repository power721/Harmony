# Project Overview

**Harmony** is a desktop music player built with:

- Python
- PySide6 (Qt6 GUI)
- SQLite
- mutagen (audio metadata)

Main capabilities:

- Local music library
- Playlists
- Lyrics (LRC sync)
- Album art
- Cloud playback (Quark Drive)
- Persistent play queue
- Global hotkeys

The project prioritizes:

- modular architecture
- thread safety
- responsive UI
- extensibility for cloud sources

---

# How To Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run application:

```bash
python main.py
```

Run tests:

```bash
python -m pytest tests/
```

---

# Key Paths

Database:

```
./music_player.db
```

Tests:

```
tests/
```

---

# Architecture

The project follows a **layered architecture**.

```
database/
player/
services/
ui/
utils/
```

AI agents should maintain this separation.

Never mix UI logic, database logic, and playback logic.

---

# Module Responsibilities

## database

Responsible for **data persistence**.

Important components:

- `DatabaseManager`
- `models.py`

Key rule:

Each thread must use **its own SQLite connection**.

This is implemented using:

```
threading.local()
```

Never share SQLite connections across threads.

---

## player

Handles playback control and queue management.

Important classes:

### PlayerEngine

Low‑level wrapper around:

```
QMediaPlayer
```

Responsibilities:

- audio playback
- playback signals

---

### PlaybackManager

Primary controller of the system.

Responsibilities:

- playback orchestration
- queue management
- local/cloud unification
- queue persistence
- download coordination

Most playback logic should live here.

---

### PlaylistItem

Unified abstraction representing:

- local track
- cloud file

Used across the player so the engine treats all sources the same.

---

## services

Services handle **external data or background work**.

Key services:

- MetadataService
- CoverService
- LyricsService
- LyricsLoader
- QuarkDriveService
- CloudDownloadService

Rules:

- services should avoid UI logic
- services should return clean data structures

---

## ui

Contains all PySide6 UI components.

Main components:

- MainWindow
- LibraryView
- PlaylistView
- QueueView
- PlayerControls
- MiniPlayer
- CloudDriveView
- LyricsWidget

UI should communicate through signals and the EventBus.

Avoid direct coupling between widgets and services.

---

## utils

Shared utilities.

Important modules:

- ConfigManager
- event_bus
- i18n
- global_hotkeys
- lrc_parser
- helpers

---

# EventBus Pattern

The project uses a global singleton EventBus for decoupled communication.

Typical usage:

```python
bus = EventBus.instance()
bus.track_changed.connect(handler)
```

Typical events:

- track_changed
- playback_state_changed
- position_changed
- download_progress
- lyrics_loaded
- tracks_added

UI components should subscribe to events instead of tightly coupling to services.

---

# Cloud Playback Flow

Cloud files are integrated through PlaylistItem.

Typical flow:

1. User selects cloud file
2. PlaybackManager creates PlaylistItem(needs_download=True)
3. CloudDownloadService downloads file
4. On completion playback begins

Cloud downloads run in background threads.

---

# Search

Track search uses:

```
SQLite FTS5
```

Indexed fields:

- title
- artist
- album

Fallback search:

```
LIKE queries
```

---

# Queue Persistence

Playback queue is persisted in the database.

Managed by:

```
PlaybackManager.save_queue()
PlaybackManager.restore_queue()
```

The queue supports:

- local tracks
- cloud tracks

Queue is restored on startup.

---

# Concurrency Model

Important rules:

- database uses thread‑local connections
- downloads run in background threads
- lyrics loading runs in QThread
- UI thread must remain responsive

Communication between threads must use Qt signals.

---

# Coding Patterns

Preferred patterns:

- dataclasses for models
- service classes for external logic
- signal‑driven UI updates
- centralized state management
- minimal UI‑service coupling

---

# Testing Rules

All tests are located in:

```
tests/
```

Use:

```
pytest
```

AI agents must ensure tests pass before completing tasks.

---

# AI Development Rules

## Rule 1 — Update README

When **new features are added**, update:

```
README.md
```

---

## Rule 2 — Update Tests

When **adding features or fixing bugs**:

- update or add tests
- ensure:

```
pytest tests/
```

passes.

---

## Rule 3 — Update CLAUDE.md

When **major architecture or workflow changes occur**, update:

```
CLAUDE.md
```

so future AI agents understand the project.

---

# Goals For AI Agents

When modifying the project:

1. Preserve layered architecture
2. Maintain thread safety
3. Keep UI responsive
4. Avoid tight coupling
5. Write tests for new behavior
