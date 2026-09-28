"""Graceful shutdown for the standalone bot processes."""

from contextlib import contextmanager
import signal
from threading import Event


@contextmanager
def shutdown_event():
    """Stop between operations and restore the caller's signal handlers on exit."""
    stop = Event()

    def request_stop(signum, frame):
        stop.set()

    previous = {
        signum: signal.signal(signum, request_stop)
        for signum in (signal.SIGTERM, signal.SIGINT)
    }
    try:
        yield stop
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
