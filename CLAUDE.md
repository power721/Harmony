# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Harmony is a modern music player built with PySide6 (Qt6) and SQLite. It features a Spotify-like interface with library management, playlists, lyrics display, album art, cloud drive integration (Quark Drive), and global hotkeys.

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
  - `PlaybackManager` - **Primary controller** for unified local/cloud playback, queue persistence, and download coordination
  - `PlayerController` - Legacy controller (being replaced by PlaybackManager)
  - `PlaylistItem` - Unified abstraction for local tracks and cloud files (supports both source types)
  - `PlayMode` enum - Sequential, Loop, PlaylistLoop, Random, RandomLoop, RandomTrackLoop
  - `EqualizerWidget` - Audio equalizer with presets

- **services/** - External data fetching and processing
  - `MetadataService` - Audio metadata extraction using mutagen
  - `CoverService` - Album art fetching from online sources
  - `LyricsService` - Lyrics scraping from web sources
  - `QuarkDriveService` - Quark Drive API integration (QR login, file ops, download URLs)
  - `CloudDownloadService` - Singleton download manager with caching and progress tracking
  - `LyricsLoader` - Advanced lyrics loading with LRC file parsing

- **ui/** - PySide6 GUI components
  - `MainWindow` - Application shell with navigation, tray icon, mini player
  - `LibraryView` - Track library with search/filter
  - `PlaylistView` - Playlist management
  - `QueueView` - Current playback queue
  - `PlayerControls` - Playback control bar (seek, volume, play mode)
  - `MiniPlayer` - Floating mini player window
  - `CloudDriveView` - Cloud drive browser with QR login
  - `CloudLoginDialog` - QR code dialog for cloud account authentication
  - `LyricsWidget` / `LyricsWidgetPro` - Lyrics display with LRC synchronization

- **utils/** - Cross-cutting utilities
  - `ConfigManager` - JSON config persistence (~/.config/harmony_player/config.json)
  - `i18n` - Translation system using `t()` function, loads from translations/*.json
  - `global_hotkeys` - System-wide media key handling
  - `event_bus` - Centralized singleton EventBus for application-wide signals
  - `lrc_parser` - LRC lyrics file parser for synchronized lyrics display
  - `helpers` - Utility functions including `sanitize_filename()` for cloud files

### EventBus Pattern

The application uses a centralized singleton `EventBus` (in `utils/event_bus.py`) for decoupled component communication. Instead of direct signal connections between components, most signals flow through the EventBus:

- **Playback Events**: `track_changed`, `playback_state_changed`, `position_changed`, `duration_changed`, `play_mode_changed`, `volume_changed`, `track_finished`
- **Cloud Download Events**: `download_started`, `download_progress`, `download_completed`, `download_error`, `track_needs_download`
- **UI Events**: `lyrics_loaded`, `lyrics_error`, `metadata_updated`
- **Library Events**: `tracks_added`, `playlist_created`, `playlist_modified`, `playlist_deleted`, `favorite_changed`
- **Cloud Account Events**: `cloud_account_added`, `cloud_account_removed`, `cloud_token_updated`

Usage: `bus = EventBus.instance(); bus.track_changed.connect(handler)`

### Signal Flow Pattern

The application uses Qt's signal/slot mechanism extensively:

1. UI components emit signals (e.g., `play_track.emit(track_id)`)
2. `PlaybackManager` (primary controller) coordinates between engine, database, and services
3. `PlayerEngine` handles actual playback, emits state change signals
4. Signals are forwarded to EventBus for global consumption
5. UI components update in response to EventBus signals

### Cloud Drive Architecture

Cloud drive support (currently Quark Drive) is integrated throughout the application:

- **`QuarkDriveService`** (`services/quark_drive_service.py`) - API client for Quark Drive including QR code login, file listing, download URL generation, and account info
- **`CloudDownloadService`** (`services/cloud_download_service.py`) - Singleton service managing cloud file downloads with caching, progress tracking, and cancellation
- **`CloudDriveView`** (`ui/cloud_drive_view.py`) - UI component for browsing and playing cloud files
- **`CloudLoginDialog`** (`ui/cloud_login_dialog.py`) - QR code login dialog for cloud accounts
- **Database models**: `CloudAccount` (credentials + state), `CloudFile` (cached metadata), `PlayQueueItem` (unified local/cloud queue)

Cloud files are seamlessly integrated with local playback through the `PlaylistItem` abstraction, which unifies local tracks and cloud files with a single interface.

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

### Queue Persistence

The application maintains a persistent play queue that survives application restarts:

- Queue items are stored in the database (via `PlayQueueItem` model)
- `PlaybackManager.save_queue()` - Saves current queue, index, and play mode
- `PlaybackManager.restore_queue()` - Restores queue on startup without auto-play
- Queue supports mixed local tracks and cloud files
- Cloud file state includes navigation history (`last_fid_path`, `last_position`) for resuming

### PlaylistItem Abstraction

`PlaylistItem` (in `player/playlist_item.py`) is the core abstraction that unifies local and cloud playback:

- Properties: `is_local`, `is_cloud`, `track_id`, `cloud_file_id`, `local_path`, `needs_download`
- Factory methods: `from_track()`, `from_cloud_file()`, `from_play_queue_item()`
- Methods: `to_play_queue_item()` for persistence
- This allows the player engine to treat all sources uniformly

## Common Patterns

- **Models**: Use `@dataclass` for simple data containers (Track, Playlist, etc.)
- **Services**: Classmethods for stateless operations (MetadataService.extract_metadata())
- **Singletons**: EventBus and CloudDownloadService use singleton pattern with `.instance()` classmethod
- **State Management**: Qt signals for reactive updates, QSettings for persistence, EventBus for global events
- **Error Handling**: Services silently return None/defaults on failure, UI shows fallback values
- **Logging**: All modules use Python's logging module with consistent format: `'[%(levelname)s] %(name)s - %(message)s'`

## Important Patterns

### Cloud File Download Flow

1. User selects cloud file to play
2. `PlaybackManager` creates `PlaylistItem` with `needs_download=True`
3. Engine emits `track_needs_download` signal via EventBus
4. `CloudDownloadService` starts download in background thread
5. Download progress signals emitted via EventBus
6. On completion, `PlaybackManager.on_download_completed()` updates playlist item and starts playback

### State Restoration on Startup

The application restores previous state on launch:
1. `PlaybackManager.restore_queue()` - Loads saved play queue
2. Restores play mode, volume, and current index from ConfigManager
3. Determines source type (local/cloud) from saved queue
4. For cloud: restores account, navigation history, and last playback position
5. Does NOT auto-play; user must press play

### Thread Safety

- DatabaseManager uses thread-local storage for SQLite connections
- Cloud downloads run in QThread workers (CloudDownloadWorker)
- Qt signals are thread-safe for cross-thread communication
