# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Harmony is a modern music player built with PySide6 (Qt6) and SQLite. It features a Spotify-like interface with library management, playlists, lyrics display, album art, and global hotkeys.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Database location
./music_player.db (SQLite database in project root)
```

## Architecture

### Layered Architecture

The application follows a clear separation of concerns across modules:

- **database/** - SQLite data persistence with thread-local connections
  - `DatabaseManager` - All database operations with thread-safe connection handling
  - `models.py` - Dataclass models: Track, Playlist, PlaylistItem, PlayHistory, Favorite

- **player/** - Audio playback engine and control logic
  - `PlayerEngine` - Low-level QMediaPlayer wrapper, emits signals for state changes
  - `PlayerController` - High-level controller bridging engine + database, handles history/favorites
  - `PlayMode` enum - Sequential, Loop, PlaylistLoop, Random, RandomLoop, RandomTrackLoop

- **services/** - External data fetching and processing
  - `MetadataService` - Audio metadata extraction using mutagen
  - `CoverService` - Album art fetching from online sources
  - `LyricsService` - Lyrics scraping from web sources

- **ui/** - PySide6 GUI components
  - `MainWindow` - Application shell with navigation, tray icon, mini player
  - `LibraryView` - Track library with search/filter
  - `PlaylistView` - Playlist management
  - `QueueView` - Current playback queue
  - `PlayerControls` - Playback control bar (seek, volume, play mode)
  - `MiniPlayer` - Floating mini player window

- **utils/** - Cross-cutting utilities
  - `ConfigManager` - JSON config persistence (~/.config/harmony_player/config.json)
  - `i18n` - Translation system using `t()` function, loads from translations/*.json
  - `global_hotkeys` - System-wide media key handling

### Signal Flow Pattern

The application uses Qt's signal/slot mechanism extensively:

1. UI components emit signals (e.g., `play_track.emit(track_id)`)
2. `PlayerController` receives signals, coordinates with database
3. `PlayerEngine` handles actual playback, emits state change signals
4. UI components update in response to engine signals

### Database Threading Model

`DatabaseManager` uses thread-local storage (`threading.local()`) to ensure each thread has its own SQLite connection. This is critical for Qt applications where UI and worker threads may access the database concurrently.

### Configuration Persistence

Two separate config systems:
- `QSettings` (Qt) - UI preferences like language, window geometry
- `ConfigManager` (JSON) - Player state like volume, play mode

### Internationalization

- Use `t(key, default)` for translatable strings
- Translation files in `translations/*.json`
- Language switched via `set_language(lang)` where lang is "en" or "zh"
- Language preference persisted in QSettings

### Audio Format Support

Supported formats (via MetadataService.SUPPORTED_FORMATS): `.mp3`, `.flac`, `.ogg`, `.oga`, `.m4a`, `.mp4`, `.wma`, `.wav`

## Common Patterns

- **Models**: Use `@dataclass` for simple data containers (Track, Playlist, etc.)
- **Services**: Classmethods for stateless operations (MetadataService.extract_metadata())
- **State Management**: Qt signals for reactive updates, QSettings for persistence
- **Error Handling**: Services silently return None/defaults on failure, UI shows fallback values
