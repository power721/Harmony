# Harmony - Modern Music Player

A modern desktop music player built with Python and PySide6, featuring clean architecture design and seamless playback of local and cloud music.

## Features

### 🎵 Local Music Playback
- **Music Library Management** - Scan and manage local music files
- **Intelligent Metadata Extraction** - Automatically extract audio file tag information (title, artist, album, etc.)
- **Album Cover Display** - Automatically fetch and display album covers
- **Multiple Audio Formats** - Support for MP3, FLAC, OGG, M4A, WAV, WMA, and more
- **Full-Text Search** - Fast song search based on SQLite FTS5 with fuzzy matching

### ☁️ Cloud Music Integration
- **Quark Drive Support** - Login to Quark Drive via QR code
- **Online Browsing** - Directly browse music files in cloud storage
- **Smart Download** - Automatically download cloud music to local cache
- **Hybrid Playback** - Seamless switching between local and cloud music

### 🎧 QQ Music Integration
- **Online Music Browsing** - Browse QQ Music charts, playlists, albums, and artists
- **Multi-dimensional Search** - Search for songs, albums, artists, and playlists
- **Local QR Login** - Support for both QQ and WeChat login methods
- **QR Code Login** - Auto-generate QR code for mobile scanning
- **Credential Management** - Automatically save login credentials
- **Multiple Quality Support** - Support for various qualities (Master, Dolby Atmos, Lossless, MP3)
- **Lyrics Retrieval** - Support for translated and word-by-word lyrics
- **Cover Art Retrieval** - Direct access to album covers and artist images
- **Smart Queue Operations** - Support playing current page or all pages, insert or append to queue

### 📋 Playlist Management
- **Custom Playlists** - Create and manage playlists
- **Playback Queue** - Real-time view and management of current playback queue
- **Drag & Drop Sorting** - Drag to reorder songs in the queue
- **Queue Persistence** - Restore playback queue after app restart

### ⏯️ Playback Control
- **Complete Playback Controls** - Play/Pause/Previous/Next
- **Multiple Playback Modes** - Sequential, shuffle, list loop, single repeat
- **Progress Control** - Precise playback progress control
- **Sleep Timer** - Support countdown and play count modes, can stop playback, exit app, or shutdown computer
- **Smart Queue Management** - Support insert to queue and append to queue operations, handle current page or all pages
- **Download Failure Handling** - Automatically mark failed cloud downloads, support retry

### 🎤 Lyrics Features
- **Auto Download Lyrics** - Automatically fetch lyrics from the internet
- **Multiple Sources** - LRCLIB, NetEase Cloud Music, Kugou Music, QQ Music
- **Smart Matching** - Intelligent matching algorithm based on title, artist, album, duration
- **LRC Format Support** - Support for .lrc lyrics file parsing
- **Synchronized Display** - Lyrics sync with playback progress
- **Advanced Lyrics Window** - Support scrolling and highlighting
- **Traditional-Simplified Conversion** - Automatically convert Traditional Chinese lyrics to Simplified

### 🖼️ Cover Management
- **Auto Cover Retrieval** - Automatically fetch album covers from the internet (NetEase Cloud Music, iTunes, MusicBrainz, Last.fm)
- **Smart Matching** - Precise cover matching using MatchScorer algorithm
- **Unified Cover Download** - Unified cover download dialog for tracks, albums, and artists
- **Strategy Pattern Architecture** - Use strategy pattern to handle different cover search types
- **Manual Cover Download** - Support manual selection and download of album covers (NetEase Cloud Music, QQ Music, iTunes, Last.fm)
- **Artist Covers** - Search and download artist covers (NetEase Cloud Music, QQ Music, iTunes)
- **Cover Preview** - Preview cover effect before downloading

### 🤖 AI Metadata Enhancement
- **AI Tag Recognition** - Use AI models to intelligently extract music metadata from filenames
- **Auto Completion** - Automatically complete missing title, artist, album information
- **OpenAI Compatible** - Support all OpenAI-compatible AI APIs
- **Audio Fingerprinting** - Identify unknown music through AcoustID

### 🎨 Modern Interface
- **Spotify-Style Design** - Minimalist modern UI design with dynamic theme color extraction
- **Frameless Window** - Custom title bar with integrated window control buttons
- **Mini Player** - Compact floating playback window with drag support
- **System Tray** - Minimize to system tray for background playback
- **Responsive Layout** - Adapt to different screen sizes
- **Album/Artist Views** - Card-style browsing of albums and artists

### ⌨️ Other Features
- **Global Hotkeys** - Support system-level media key controls
- **Playback History** - Automatically record playback history
- **Favorites** - Favorite loved songs
- **Multi-language Support** - Chinese/English interface switching
- **State Recovery** - Restore playback state after restart

## Installation

### Requirements

- Python 3.10 or higher
- Supported operating systems: Windows, Linux, macOS

### Installation Steps

```bash
# Clone repository
git clone https://github.com/power721/music-player.git
cd music-player

# Install dependencies
uv sync

# Download bundled fonts (optional, for development)
./download_fonts.sh

# Run application
uv run python main.py
```

### Font Bundling

Harmony bundles fonts for consistent cross-platform display:
- **Inter** - Western UI font
- **Noto Sans SC** - Simplified Chinese font
- **Noto Color Emoji** - Emoji support

For development, run `./download_fonts.sh` to download fonts. For production builds, fonts are automatically bundled by PyInstaller.

See `docs/font-bundling.md` for detailed documentation.

### Dependencies

Dependencies are managed by `pyproject.toml` and installed using uv:

| Dependency | Purpose |
|------------|---------|
| PySide6 | Qt6 GUI Framework |
| mutagen | Audio metadata extraction |
| requests | HTTP requests |
| beautifulsoup4 | Lyrics scraping |
| lxml | HTML parsing |
| pymediainfo | Media information extraction |
| qrcode | QR code generation |
| openai | AI metadata enhancement |
| opencc-python-reimplemented | Traditional-Simplified conversion |
| pyacoustid | Audio fingerprinting |
| qqmusic-api-python | QQ Music API |
| pycryptodome | Encryption/decryption (QQ Music) |

## Usage Guide

### Local Music

1. Click the "Add Music" button in the bottom left
2. Select a folder containing music files
3. Music will be scanned and added to the library
4. Click a song to play

### Cloud Music

1. Click the "Cloud" tab in the sidebar
2. Click the "Login" button to display QR code
3. Scan the QR code with your mobile Quark Drive app to login
4. Browse cloud folders and click music files to start playback
5. Music will automatically download to the local cache directory

### QQ Music Login

1. Go to Settings -> QQ Music Configuration
2. Click the "Scan to Login" button
3. Select login method: QQ or WeChat
4. Scan the QR code with mobile QQ or WeChat
5. Confirm login on your phone
6. Credentials will be automatically saved after successful login

### Playback Control

- **Play/Pause**: Click the play button in the bottom control bar or press Space
- **Skip**: Use previous/next track buttons
- **Progress Control**: Drag the progress bar or click on the progress bar position
- **Volume Control**: Drag the volume slider
- **Playback Mode**: Click the playback mode button to switch

### Keyboard Shortcuts

**Main Window Shortcuts:**
- `Space` - Play/Pause
- `Ctrl + →` - Next track
- `Ctrl + ←` - Previous track
- `Ctrl + ↑` - Volume up
- `Ctrl + ↓` - Volume down
- `Ctrl + F` - Toggle favorite
- `Ctrl + P` - Toggle now playing / main window
- `Ctrl + M` - Toggle mini mode
- `Esc` - Toggle now playing / main window
- `Ctrl + Q` - Quit application
- `F1` - Show help

**Now Playing Shortcuts:**
- `Space` - Play/Pause
- `Ctrl + →` - Next track
- `Ctrl + ←` - Previous track
- `Ctrl + ↑` - Volume up
- `Ctrl + ↓` - Volume down
- `Ctrl + M` - Switch to mini player
- `Ctrl + P` - Back to main window
- `Ctrl + Q` - Quit application

**Mini Player Shortcuts:**
- `Space` - Play/Pause
- `Ctrl + →` - Next track
- `Ctrl + ←` - Previous track
- `Ctrl + ↑` - Volume up
- `Ctrl + ↓` - Volume down
- `Ctrl + M` - Close mini player
- `Ctrl + P` - Switch to now playing
- `Ctrl + Q` - Quit application

## Architecture

### Tech Stack

- **GUI Framework**: PySide6 (Qt6)
- **Audio Engine**: Qt Multimedia (QMediaPlayer)
- **Database**: SQLite3 with FTS5
- **Metadata Extraction**: mutagen, pymediainfo
- **Network Requests**: requests
- **Lyrics Parsing**: BeautifulSoup4, lxml

### Core Architecture (Harmony 3.0)

The project adopts a **clean layered architecture** with dependency inversion for loose coupling:

```
app/           → Application bootstrap and dependency injection
domain/        → Pure domain models (no external dependencies)
repositories/  → Data access abstraction layer
services/      → Business logic layer
infrastructure/→ Technical implementation layer
ui/            → PySide6 user interface
system/        → Application-level components
utils/         → Utility classes
```

### Layer Dependencies

```
UI → Services → Repositories → Infrastructure
              ↘ Domain ↗
```

- **UI** only depends on **Services** and **Domain**
- **Services** depend on **Repositories** and **Domain**
- **Repositories** depend on **Infrastructure** and **Domain**
- **Domain** has no dependencies (pure data classes)
- **Infrastructure** implements technical details

### Directory Structure

```
Harmony/
├── app/                    # Application bootstrap and dependency injection
│   ├── application.py      # Application singleton
│   └── bootstrap.py        # Dependency injection container
├── domain/                 # Domain models (pure data classes)
│   ├── track.py           # Music track entity
│   ├── playlist.py        # Playlist entity
│   ├── playlist_item.py   # Playlist item abstraction
│   ├── playback.py        # Playback state enumeration
│   ├── cloud.py           # Cloud entity
│   ├── album.py           # Album aggregate entity
│   ├── artist.py          # Artist aggregate entity
│   └── history.py         # Playback history
├── repositories/           # Data access layer
│   ├── track_repository.py
│   ├── playlist_repository.py
│   ├── cloud_repository.py
│   ├── queue_repository.py
│   └── interfaces.py       # Repository interfaces
├── services/               # Business logic layer
│   ├── playback/          # Playback services
│   │   ├── playback_service.py
│   │   └── queue_service.py
│   ├── library/           # Library service
│   │   └── library_service.py
│   ├── lyrics/            # Lyrics services
│   │   ├── lyrics_service.py
│   │   └── lyrics_loader.py
│   ├── metadata/          # Metadata services
│   │   ├── metadata_service.py
│   │   └── cover_service.py
│   ├── cloud/             # Cloud services
│   │   ├── quark_service.py
│   │   ├── download_service.py
│   │   └── qqmusic/       # QQ Music services
│   │       ├── qqmusic_service.py
│   │       ├── client.py
│   │       ├── crypto.py
│   │       └── common.py
│   └── ai/                # AI services
│       ├── ai_metadata_service.py
│       └── acoustid_service.py
├── infrastructure/         # Technical implementation layer
│   ├── audio/             # Audio engine
│   │   └── audio_engine.py
│   ├── database/          # Database
│   │   └── sqlite_manager.py
│   ├── network/           # Network client
│   │   └── http_client.py
│   └── cache/             # File cache
│       └── file_cache.py
├── ui/                     # User interface
│   ├── windows/           # Windows
│   │   ├── main_window.py
│   │   └── mini_player.py
│   ├── views/             # Views
│   │   ├── library_view.py
│   │   ├── playlist_view.py
│   │   ├── queue_view.py
│   │   └── cloud_view.py
│   └── widgets/           # Widgets
│       ├── player_controls.py
│       ├── lyrics_widget_pro.py
│       ├── cover_download_dialog.py
│       ├── album_cover_download_dialog.py
│       ├── artist_cover_download_dialog.py
│       ├── settings_dialog.py
│       ├── cloud_login_dialog.py
│       ├── qqmusic_qr_login_dialog.py
│       ├── equalizer_widget.py
│       ├── help_dialog.py
│       ├── album_card.py
│       └── artist_card.py
├── system/                 # System components
│   ├── config.py          # Configuration management
│   ├── event_bus.py       # Event bus
│   ├── i18n.py            # Internationalization
│   └── hotkeys.py         # Global hotkeys
├── utils/                  # Utilities
│   ├── helpers.py         # Helper functions
│   ├── lrc_parser.py      # LRC parser
│   └── match_scorer.py    # Smart matching algorithm
├── tests/                  # Tests
│   ├── test_domain/       # Domain model tests
│   ├── test_services/     # Service layer tests
│   ├── test_repositories/ # Data access layer tests
│   ├── test_infrastructure/ # Infrastructure tests
│   ├── test_ui/           # UI tests
│   ├── test_utils/        # Utility tests
│   └── test_system/       # System component tests
├── translations/           # Translation files
│   ├── en.json
│   └── zh.json
└── main.py                 # Application entry point
```

### Key Design Patterns

- **Dependency Injection**: Manage component dependencies through Bootstrap container
- **EventBus Pattern**: Centralized event bus for decoupled component communication
- **Singleton Pattern**: EventBus, Bootstrap, CloudDownloadService use singletons
- **Factory Pattern**: PlaylistItem uses factory methods to create different playlist item types
- **Thread-Local Storage**: DatabaseManager uses thread-local for thread safety
- **Data Class Pattern**: Use `@dataclass` to define domain models

### Core Abstractions

**PlaylistItem** - Unified playlist item abstraction supporting local and cloud files:
- `is_local` / `is_cloud` - Determine source type
- `needs_download` - Whether cloud file needs download
- `from_track()` / `from_cloud_file()` - Factory methods
- `to_play_queue_item()` - Convert to persistence model

**MatchScorer** - Intelligent matching algorithm:

Dual-mode scoring system:
- **Lyrics Mode** (title-priority): Title 35%, Artist 30%, Album 15%, Duration 20%
- **Cover Mode** (album-priority): Title 15%, Artist 30%, Album 35%, Duration 20%

Scoring features:
- Exact match: 100 points for complete match
- Normalized matching: Ignore case, punctuation, spaces
- Smart noise removal: Auto-remove common suffixes like "(Official)", "[MV]", "(Lyric Video)"
- Multi-artist handling: Support "feat.", "&", "," separators, extract primary artist
- Duration tolerance: ±30 seconds considered exact match, proportional deduction beyond
- Word overlap: Calculate partial match using Jaccard similarity
- QQ Music priority: Prefer QQ Music source when scores are equal

Total score range: 0-100, higher indicates better match

**EventBus** - Centralized event signals:
- Playback events: `track_changed`, `playback_state_changed`, `position_changed`
- Download events: `download_started`, `download_progress`, `download_completed`
- UI events: `lyrics_loaded`, `metadata_updated`, `cover_updated`
- Library events: `tracks_added`, `playlist_created`, `favorite_changed`

## Data Storage

### Database (Harmony.db)

All data is stored uniformly in an SQLite database.

- **Location**: `./Harmony.db` (project root)

**Table Structure**:
- `tracks` - Local music library
- `albums` - Album aggregation
- `artists` - Artist aggregation
- `playlists` / `playlist_items` - Playlists
- `play_history` - Playback history
- `favorites` - Favorites
- `cloud_accounts` - Cloud accounts
- `cloud_files` - Cloud file cache
- `play_queue` - Persistent playback queue
- **`settings`** - Application configuration storage (unified config management)

### Settings Table

Application configuration (playback mode, volume, AI settings, etc.) is stored in the `settings` table:

**Stored Content**:
- Player settings: Volume, playback mode, playback source
- Playback state: Current track ID, playback position
- Cloud settings: Account ID, download directory
- UI settings: Language, window geometry, view type
- AI settings: API URL, key, model
- AcoustID settings: API key

**Table Structure**:
```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Translation Files

- **Location**: `translations/*.json`
- **Supported Languages**: Chinese (zh), English (en)

## Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run specific test modules
uv run pytest tests/test_domain/
uv run pytest tests/test_repositories/

# Show test coverage
uv run pytest tests/ -v

# Manual testing
uv run python main.py
```

### Test Coverage

The project includes 270+ unit tests covering:
- **Domain Models**: Track, Playlist, PlaylistItem, Playback, Cloud, Album, Artist, History
- **Data Access Layer**: TrackRepository, PlaylistRepository, QueueRepository
- **Service Layer**: LibraryService, MetadataService
- **Infrastructure**: FileCache, HttpClient
- **Utilities**: Helpers, LrcParser, MatchScorer
- **System Components**: EventBus

### Code Style

The project follows these code style guidelines:
- Use PEP 8 standards
- Type annotations using `typing` module
- Data classes using `@dataclass` decorator
- Logging using Python logging module
- Log format: `'[%(levelname)s] %(name)s - %(message)s'`

### Architecture Rules

AI developers should follow these rules:
1. Maintain clear layered architecture
2. Domain layer must not import other modules
3. UI can only depend on Services and Domain
4. Services should avoid UI logic
5. Use EventBus for cross-component communication
6. Maintain thread safety

## Packaging & Distribution

The project provides cross-platform packaging scripts:

```bash
# Linux
./build_linux.sh

# macOS
./build_macos.sh

# Windows
build_windows.bat
```

See [BUILD.md](BUILD.md) for details.

## FAQ

### Q: Why does cloud music playback fail?
A: Please ensure:
- Successfully logged into Quark Drive account
- Network connection is normal
- Cloud file is a supported audio format

### Q: QQ Music login failed?
A: Check:
- Is network connection normal
- Is `qqmusic-api-python` dependency installed
- Has QR code expired (valid for about 2 minutes)

### Q: Lyrics not displaying?
A: Check:
- Is network connection normal
- Does lyrics file have same name as audio file (.lrc format)
- Try manually downloading lyrics

### Q: How to restore playback state after app crash?
A: The app automatically saves playback queue and state, and will automatically restore it after restart (will not auto-play).

### Q: What does the mini player window title display?
A: When playing, shows "Song Name - Artist", when paused/stopped, shows app name.

### Q: How to use AI metadata enhancement?
A: Configure AI API in settings (supports OpenAI-compatible interfaces), then select songs in the library for metadata enhancement.

## License

This project is licensed under the MIT License - see LICENSE file for details

## Acknowledgments

- Qt community for the excellent framework
- mutagen for audio metadata processing
- LRCLIB for free lyrics API
- All contributors for their support

## Contact

- Project Homepage: [GitHub Repository](https://github.com/power721/music-player)
- Issue Tracker: [GitHub Issues](https://github.com/power721/music-player/issues)
