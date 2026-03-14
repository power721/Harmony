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

# Architecture (Harmony 3.0)

The project follows a **clean layered architecture** with dependency inversion:

```
app/           → Application bootstrap and dependency injection
domain/        → Pure domain models (no dependencies)
repositories/  → Data access abstraction layer
services/      → Business logic layer
infrastructure/→ Technical implementations
ui/            → PySide6 user interface
system/        → Application-wide components
```

## Layer Dependencies

```
UI → Services → Repositories → Infrastructure
              ↘ Domain ↗
```

- **UI** only depends on **Services** and **Domain**
- **Services** depend on **Repositories** and **Domain**
- **Repositories** depend on **Infrastructure** and **Domain**
- **Domain** has no dependencies (pure dataclasses)
- **Infrastructure** implements technical details

AI agents should maintain this separation.

Never mix UI logic, database logic, and playback logic.

---

# Module Responsibilities

## app

Application bootstrap and dependency injection.

Important components:

- `Application` - Application singleton
- `Bootstrap` - Dependency injection container

---

## domain

Pure domain models with **no external dependencies**.

Important components:

- `Track`, `PlaylistItem` - Music track entities
- `Playlist` - Playlist entity
- `CloudFile`, `CloudAccount` - Cloud storage entities
- `PlayMode`, `PlaybackState` - Playback enumerations

Key rule:

Domain models must **never import** from other modules.

---

## repositories

Data access abstraction layer.

Important components:

- `TrackRepository` - Track data access
- `PlaylistRepository` - Playlist data access
- `CloudRepository` - Cloud account/file data access
- `QueueRepository` - Play queue persistence

Key rule:

Repositories abstract database operations from business logic.

---

## services

Business logic layer organized by domain.

Important subdirectories:

- `playback/` - PlaybackService, QueueService
- `library/` - LibraryService
- `lyrics/` - LyricsService, LyricsLoader
- `metadata/` - MetadataService, CoverService
- `cloud/` - QuarkService, CloudDownloadService
- `ai/` - AiMetadataService, AcoustidService

Rules:

- services should avoid UI logic
- services should return clean data structures

---

## infrastructure

Technical implementations.

Important components:

- `audio/` - AudioEngine (QMediaPlayer wrapper)
- `database/` - SqliteManager
- `network/` - HttpClient
- `cache/` - FileCache

---

## ui

Contains all PySide6 UI components.

Structure:

- `windows/` - MainWindow, MiniPlayer
- `views/` - LibraryView, PlaylistView, QueueView, CloudView
- `widgets/` - PlayerControls, LyricsWidget, dialogs

UI should communicate through signals and the EventBus.

Avoid direct coupling between widgets and services.

---

## system

Application-wide components.

Important components:

- `ConfigManager` - Configuration management
- `EventBus` - Global event bus
- `i18n` - Internationalization
- `hotkeys` - Global hotkeys

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
2. PlaybackService creates PlaylistItem(needs_download=True)
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
QueueService.save()
QueueService.restore()
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
- dependency injection through Bootstrap

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

### Rule 4 - Save documentation

Save new documentation Markdown files to folder docs/

---

# Goals For AI Agents

When modifying the project:

1. Preserve layered architecture
2. Maintain thread safety
3. Keep UI responsive
4. Avoid tight coupling
5. Write tests for new behavior
