"""Bound native Frida operations on fixture-owned processes.

Frida 17.24.3's synchronous script RPC wait does not consult Cancellable.
Use a fixture-level deadline for RPC; do not pass exports_sync calls here.
"""
import threading
import frida


def call_frida(phase, function, *args, timeout=15):
    cancellable = frida.Cancellable()
    timer = threading.Timer(timeout, cancellable.cancel)
    timer.daemon = True
    with cancellable:
        timer.start()
        try:
            return function(*args)
        except frida.OperationCancelledError as error:
            raise TimeoutError(f'Frida {phase} exceeded {timeout} seconds') from error
        finally:
            timer.cancel()


def detach_session(session):
    # Process exit can have completed automatic detachment already. Calling
    # detach again has stalled CI controllers after the owned process exited.
    if session.is_detached:
        return
    try:
        call_frida('detach', session.detach)
    except frida.InvalidOperationError:
        if not session.is_detached:
            raise
