from infrastructure.network.http_client import HttpClient


def test_shared_client_registers_atexit_cleanup(monkeypatch):
    registrations = []
    HttpClient._shared_clients = {}
    HttpClient._atexit_registered = False

    monkeypatch.setattr(
        "infrastructure.network.http_client.atexit.register",
        lambda callback: registrations.append(callback),
    )

    client = HttpClient.shared(timeout=5)

    assert client is not None
    assert len(registrations) == 1
