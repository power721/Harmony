# Tests

Test suite for Harmony Music Player.

## Structure

```
tests/
├── conftest.py                    # Pytest configuration and fixtures
├── test_domain/                   # Domain layer tests
│   ├── test_track.py             # Track model tests
│   ├── test_playlist.py          # Playlist model tests
│   ├── test_playlist_item.py     # PlaylistItem model tests
│   ├── test_playback.py          # PlayMode, PlaybackState, PlayQueueItem tests
│   └── test_cloud.py             # Cloud models tests
└── test_infrastructure/          # Infrastructure layer tests
    ├── test_file_cache.py        # FileCache tests
    └── test_http_client.py       # HttpClient tests
```

## Running Tests

Run all tests:

```bash
python -m pytest tests/
```

Run with verbose output:

```bash
python -m pytest tests/ -v
```

Run specific test file:

```bash
python -m pytest tests/test_domain/test_track.py
```

Run specific test class:

```bash
python -m pytest tests/test_domain/test_track.py::TestTrack
```

Run specific test method:

```bash
python -m pytest tests/test_domain/test_track.py::TestTrack::test_display_name_with_title
```

## Test Coverage

- **Domain Layer**: 100% coverage of core domain models
  - Track, Playlist, PlaylistItem
  - PlayMode, PlaybackState, PlayQueueItem
  - CloudProvider, CloudAccount, CloudFile

- **Infrastructure Layer**: Core components tested
  - FileCache (caching for cloud downloads)
  - HttpClient (HTTP request wrapper)

## Adding New Tests

When adding new features, follow these patterns:

1. **Domain Models**: Test dataclass initialization, properties, and business logic
2. **Infrastructure**: Mock external dependencies (network, file system)
3. **Use Fixtures**: Define sample data in `conftest.py` for reuse
4. **Follow Naming**: Use `test_<method>_<scenario>` format

## Test Categories

Tests can be marked with categories:

- `unit`: Fast, isolated tests (default)
- `integration`: Tests requiring multiple components
- `slow`: Tests that take longer to run

Example:
```bash
# Skip slow tests
python -m pytest tests/ -m "not slow"

# Only run unit tests
python -m pytest tests/ -m "unit"
```
