# Sleep Timer Feature Documentation

## Overview

The sleep timer feature allows users to automatically stop playback, quit the application, or shutdown the system after a specified time period or number of tracks.

## Features

### Timer Modes

1. **Time Mode (倒计时模式)**
   - Countdown timer in hours, minutes, and seconds
   - Maximum duration: 23 hours, 59 minutes, 59 seconds

2. **Track Count Mode (播放计数模式)**
   - Counts down based on number of tracks played
   - Range: 1-999 tracks

### Actions

1. **Stop Playback (停止播放)**
   - Stops playback but keeps the application running

2. **Quit Application (退出应用)**
   - Stops playback and closes the application
   - Equivalent to manually closing the app

3. **Shutdown System (关闭电脑)**
   - Stops playback and initiates system shutdown
   - Cross-platform support:
     - Windows: `shutdown /s /t 0`
     - Linux/macOS: `shutdown now`

### Additional Features

1. **Volume Fade Out (渐弱音量)**
   - Gradually reduces volume over 10 seconds before action
   - Smooth transition to avoid sudden silence
   - 20 fade steps at 500ms intervals

2. **Real-time Status Display**
   - Shows remaining time in HH:MM:SS format
   - Shows remaining track count
   - Updates every second

3. **Cancel Function**
   - Cancel timer at any time
   - Restores original volume if fade out was in progress

## User Interface

### Accessing the Sleep Timer

1. Click the "⏰ Sleep Timer" button in the sidebar
2. The sleep timer dialog will appear

### Using the Sleep Timer Dialog

1. **Select Mode**
   - Choose "倒计时模式" (Time Mode) or "播放计数模式" (Track Count Mode)

2. **Set Duration**
   - For Time Mode: Set hours, minutes, seconds
   - For Track Mode: Set number of tracks

3. **Choose Action**
   - Select from dropdown: Stop/Quit/Shutdown

4. **Configure Fade Out**
   - Check "渐弱音量" to enable gradual volume reduction

5. **Start Timer**
   - Click "开始" (Start) button

6. **Monitor Progress**
   - Status label shows remaining time/tracks
   - Updates in real-time

7. **Cancel Timer**
   - Click "取消定时" (Cancel) button

## Architecture

### Service Layer

**File**: `services/playback/sleep_timer_service.py`

#### SleepTimerConfig (Dataclass)
```python
@dataclass
class SleepTimerConfig:
    mode: str  # 'time' | 'track'
    value: int  # seconds | track_count
    action: str  # 'stop' | 'quit' | 'shutdown'
    fade_out: bool
```

#### SleepTimerService (QObject)
- **Responsibilities**:
  - Manages timer state and countdown
  - Handles track finished events
  - Executes actions (stop/quit/shutdown)
  - Implements volume fade out
  - Emits signals for UI updates

- **Properties**:
  - `is_active: bool` - Timer running state
  - `remaining: int` - Remaining seconds or tracks
  - `config: SleepTimerConfig` - Current configuration

- **Methods**:
  - `start(config: SleepTimerConfig)` - Start timer
  - `cancel()` - Cancel active timer

- **Signals**:
  - `remaining_changed(int)` - Remaining count updated
  - `timer_started()` - Timer started
  - `timer_stopped()` - Timer cancelled
  - `timer_triggered()` - Timer completed and action executed

### UI Layer

**File**: `ui/dialogs/sleep_timer_dialog.py`

#### SleepTimerDialog (QDialog)
- **Features**:
  - Frameless window with rounded corners
  - Theme-aware styling
  - Draggable by title area
  - Drop shadow effect
  - Real-time status updates

- **UI Components**:
  - Radio buttons for mode selection
  - Spin boxes for time/track input
  - Combo box for action selection
  - Checkbox for fade out option
  - Start/Cancel/Close buttons
  - Status label for progress display

### Integration Points

#### Bootstrap (Dependency Injection)
**File**: `app/bootstrap.py`

```python
@property
def sleep_timer_service(self) -> SleepTimerService:
    """Get sleep timer service."""
    if self._sleep_timer_service is None:
        from services.playback.sleep_timer_service import SleepTimerService
        self._sleep_timer_service = SleepTimerService(
            playback_service=self.playback_service,
            event_bus=self.event_bus
        )
    return self._sleep_timer_service
```

#### Sidebar (UI Entry Point)
**File**: `ui/windows/components/sidebar.py`

- Added `sleep_timer_requested` signal
- Added sleep timer button with ⏰ icon
- Button styled consistently with settings button

#### MainWindow (Signal Connection)
**File**: `ui/windows/main_window.py`

```python
# Connect sidebar signal
sidebar.sleep_timer_requested.connect(self._show_sleep_timer)

# Handler method
def _show_sleep_timer(self):
    """Show sleep timer dialog."""
    from ui.dialogs.sleep_timer_dialog import SleepTimerDialog
    from app.bootstrap import Bootstrap

    sleep_timer_service = Bootstrap.instance().sleep_timer_service
    dialog = SleepTimerDialog(sleep_timer_service, self)
    dialog.exec_()
```

## Testing

### Unit Tests
**File**: `tests/test_services/test_sleep_timer_service.py`

Tests cover:
- Initial state verification
- Time mode start/cancel/countdown
- Track mode start/cancel/countdown
- Action execution (stop/quit/shutdown)
- Signal emission
- Cross-platform shutdown commands

### Running Tests
```bash
uv run pytest tests/test_services/test_sleep_timer_service.py -v
```

## Internationalization

### Translations Added

**English** (`translations/en.json`):
```json
"sleep_timer": "Sleep Timer"
```

**Chinese** (`translations/zh.json`):
```json
"sleep_timer": "定时关闭"
```

## Configuration Persistence

Currently, sleep timer settings are NOT persisted across sessions. Each session starts fresh.

Future enhancement: Save last used configuration to `ConfigManager`.

## Technical Details

### Timer Implementation

1. **Time Mode**
   - Uses `QTimer` with 1-second interval
   - Each tick decrements `remaining` counter
   - Emits `remaining_changed` signal

2. **Track Mode**
   - Listens to `EventBus.track_finished` signal
   - Decrements `remaining` on each track finish
   - Disconnects signal when timer completes

### Volume Fade Out

1. Save current volume level
2. Start fade timer (500ms interval, 20 steps = 10 seconds total)
3. Calculate step size: `original_volume // 20`
4. Each tick: `volume = max(0, current_volume - step_size)`
5. After 20 steps: execute action

### Thread Safety

- `SleepTimerService` is a `QObject`
- All timers run in UI thread (Qt event loop)
- No threading issues due to Qt's signal/slot mechanism
- Volume adjustments use `PlaybackService.set_volume()` (thread-safe)

### Error Handling

1. **Invalid Platform for Shutdown**
   - Logs warning for unsupported platforms
   - Does not crash application

2. **Timer Already Active**
   - Starting new timer cancels existing one
   - Clean transition between timers

3. **Signal Disconnection**
   - Uses try/except for track_finished disconnect
   - Prevents RuntimeError if already disconnected

## Future Enhancements

1. **Configuration Persistence**
   - Save last used settings to ConfigManager
   - Restore on dialog open

2. **Preset Timers**
   - Quick-select buttons (15 min, 30 min, 1 hour)
   - User-configurable presets

3. **Multiple Actions**
   - Combine actions (e.g., fade out + stop + quit)
   - Chain actions sequentially

4. **Visual Indicators**
   - System tray icon change when timer active
   - Title bar countdown display
   - Progress bar in mini player

5. **Smart Suggestions**
   - Suggest timer based on playlist duration
   - Learn user patterns

6. **Gradual Actions**
   - Gradually dim screen before shutdown
   - Fade out screen brightness (OS-dependent)

## Related Files

- `services/playback/sleep_timer_service.py` - Core service
- `ui/dialogs/sleep_timer_dialog.py` - UI dialog
- `ui/windows/components/sidebar.py` - Entry point
- `ui/windows/main_window.py` - Signal connection
- `app/bootstrap.py` - Dependency injection
- `translations/en.json` - English translations
- `translations/zh.json` - Chinese translations
- `tests/test_services/test_sleep_timer_service.py` - Unit tests
