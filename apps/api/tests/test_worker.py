from contextlib import contextmanager

from app.run_service import RunService
from app.run_store import RunBusyError


def test_busy_run_does_not_starve_following_queued_run(settings, monkeypatch) -> None:
    runtime = RunService(settings)
    processed = []

    class Connection:
        def execute(self, query):
            return self

        def fetchall(self):
            return [("busy-run",), ("next-run",)]

    @contextmanager
    def connect(settings):
        yield Connection()

    def execute(run_id):
        processed.append(run_id)
        if run_id == "busy-run":
            raise RunBusyError("Already processed by another worker")
        runtime.stop.set()

    monkeypatch.setattr("app.run_service.connect", connect)
    monkeypatch.setattr(runtime, "execute", execute)
    runtime._worker()
    assert processed == ["busy-run", "next-run"]
