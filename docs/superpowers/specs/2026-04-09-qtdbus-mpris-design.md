# QtDBus MPRIS Migration Design

**Goal**

Replace the Linux MPRIS implementation with a `PySide6.QtDBus`-based service so AppImage builds no longer depend on host `dbus-python` / `PyGObject` bindings, while preserving the current `org.mpris.MediaPlayer2` and `org.mpris.MediaPlayer2.Player` behavior.

**Scope**

- Applies to Linux MPRIS startup, service export, property updates, and playback command dispatch
- Keeps the existing `Bootstrap.start_mpris(...)` and `MPRISController` integration points used by [app/application.py](/home/harold/workspace/music-player/app/application.py)
- Preserves current root/player methods, player properties, metadata mapping, and property-changed signaling semantics
- Explicitly drops `org.mpris.MediaPlayer2.TrackList`
- Removes `dbus-python` and `gi` runtime probing/fallback logic from [app/bootstrap.py](/home/harold/workspace/music-player/app/bootstrap.py)
- Removes the optional Linux `dbus-python` dependency from [pyproject.toml](/home/harold/workspace/music-player/pyproject.toml)

**Design**

- Rebuild [system/mpris.py](/home/harold/workspace/music-player/system/mpris.py) around `PySide6.QtDBus`
- Keep a controller object responsible for:
  - acquiring the session bus connection
  - registering `/org/mpris/MediaPlayer2`
  - registering the `org.mpris.MediaPlayer2.musicplayer` service name
  - exposing MPRIS methods/properties/signals through QtDBus-exported QObject methods
  - forwarding all UI-affecting playback/window actions through the existing `ui_dispatcher`
- Keep the existing metadata/property helpers where they still make sense, but emit QtDBus-compatible values instead of `dbus-python` wrapper types
- Continue to publish:
  - `org.mpris.MediaPlayer2`: `Raise`, `Quit`, root properties
  - `org.mpris.MediaPlayer2.Player`: `Play`, `Pause`, `Stop`, `PlayPause`, `Next`, `Previous`, `Seek`, `SetPosition`, player properties, `Seeked`, and `PropertiesChanged`
- Do not reintroduce a compatibility layer to the old implementation; Linux should have one MPRIS backend only

**Runtime Rules**

- Linux MPRIS availability should depend only on:
  - `PySide6.QtDBus` being importable
  - a usable session bus being present
- If `QtDBus` or the session bus is unavailable, bootstrap should log a single clear warning and disable MPRIS for that run
- AppImage `AppRun` should continue to initialize `DBUS_SESSION_BUS_ADDRESS` before launching the frozen binary
- There should be no `/usr/bin/python3` probing and no host Python package fallback

**Behavior Rules**

- Existing MPRIS-visible behavior should stay intact for:
  - `PlaybackStatus`
  - `LoopStatus`
  - `Position`
  - `Metadata`
  - `Shuffle`
  - `Volume`
  - `CanControl`, `CanGoNext`, `CanGoPrevious`, `CanPlay`, `CanPause`, `CanSeek`
  - `Raise` and `Quit`
  - playback control methods dispatching onto the UI thread
- `Metadata` should continue to expose stable track IDs derived from the track identifier, title/artist/album, duration in microseconds, cover art URL, and local track URL when available
- `TrackList` interfaces and signals should be removed rather than partially preserved

**Testing**

- Replace the current `dbus-python`-stubbed unit tests in [tests/test_system/test_mpris.py](/home/harold/workspace/music-player/tests/test_system/test_mpris.py) with tests around:
  - command dispatch through the controller/service bridge
  - property payload generation for root/player interfaces
  - stable metadata/track ID generation
  - `ui_dispatcher` usage for UI-facing commands
  - behavior when the session bus or service-name registration fails
- Update [tests/test_app/test_plugin_bootstrap.py](/home/harold/workspace/music-player/tests/test_app/test_plugin_bootstrap.py) so Linux runtime readiness is expressed in terms of `QtDBus` plus session bus availability, not host `dbus-python` fallback
- Keep the packaging regression in [tests/test_release_build.py](/home/harold/workspace/music-player/tests/test_release_build.py) that ensures AppImage `AppRun` initializes D-Bus

**Risks**

- QtDBus export mechanics in PySide6 differ substantially from `dbus-python`, so signal/property exposure needs explicit verification
- Session-bus registration failure must degrade cleanly without affecting application startup
- Removing `TrackList` changes the exported interface surface; the implementation must ensure all retained interfaces still satisfy common desktop integrations
