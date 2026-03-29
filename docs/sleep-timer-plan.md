# Sleep Timer Implementation Plan

## Architecture
- **Service**: `services/playback/sleep_timer_service.py` - Core timer logic
- **UI Dialog**: `ui/dialogs/sleep_timer_dialog.py` - Configuration dialog
- **Integration**: MainWindow menu action

## Data Model
```python
@dataclass
class SleepTimerConfig:
    mode: str  # 'time' | 'track'
    value: int  # seconds | track_count
    action: str  # 'stop' | 'quit' | 'shutdown'
    fade_out: bool
```

## Implementation Steps

### 1. SleepTimerService
- QTimer for countdown mode (1s interval)
- Track EventBus.track_finished for track count mode
- Fade out volume before action
- Actions: stop/quit/shutdown
- Signals: remaining_changed(remaining: int), timer_triggered()

### 2. SleepTimerDialog
- Mode selection (radio buttons)
- Time input (QTimeEdit or spinbox)
- Track count input (QSpinBox)
- Action dropdown (QComboBox)
- Fade out checkbox
- Start/Cancel buttons
- Display remaining time/tracks

### 3. System Shutdown
- Cross-platform: Windows (`shutdown /s /t 0`), Linux/macOS (`shutdown now`)
- Needs proper permission handling

### 4. Integration Points
- Add menu action "Tools → Sleep Timer"
- Show remaining in status bar or mini player
- Persist settings to ConfigManager

## Files to Create/Modify
- `services/playback/sleep_timer_service.py` (NEW)
- `ui/dialogs/sleep_timer_dialog.py` (NEW)
- `ui/windows/main_window.py` (ADD menu item)
- `app/bootstrap.py` (INJECT service)
- `system/config_manager.py` (ADD persist config)

## Key Considerations
- Thread safety: QTimer runs in UI thread
- Volume fade: Gradual reduction over 10s
- Cancel logic: Stop timer, restore volume
- EventBus integration: track_finished signal
