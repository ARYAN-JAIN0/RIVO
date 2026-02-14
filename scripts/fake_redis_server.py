from __future__ import annotations

import signal
import sys
import threading

from fakeredis import TcpFakeServer


def main() -> int:
    host = "127.0.0.1"
    port = 6380
    server = TcpFakeServer((host, port))

    shutdown_event = threading.Event()

    def _shutdown(*_args):
        shutdown_event.set()
        server.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"fake-redis-listening:{host}:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
