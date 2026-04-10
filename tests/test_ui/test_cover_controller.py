import threading

from ui.controllers.cover_controller import CoverController


def test_cancel_all_does_not_deadlock_when_cancel_triggers_cleanup():
    controller = CoverController()

    class _Future:
        def cancel(self):
            controller._cleanup(self)
            return True

    controller._futures["search:test"] = _Future()

    worker = threading.Thread(target=controller.cancel_all, daemon=True)
    worker.start()
    worker.join(timeout=0.2)

    assert worker.is_alive() is False

    controller.shutdown()
