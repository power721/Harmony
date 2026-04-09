from unittest.mock import Mock

from services.playback.sleep_timer_service import SleepTimerService


def test_fade_step_keeps_zero_volume_path_active():
    playback_service = Mock()
    playback_service.volume = 0
    playback_service.set_volume = Mock()
    event_bus = Mock()
    event_bus.track_finished = Mock()

    service = SleepTimerService(playback_service, event_bus)
    service._original_volume = 0
    service._fade_steps = 5

    service._fade_step()

    playback_service.set_volume.assert_called_once_with(0)
    assert service._fade_steps == 4
