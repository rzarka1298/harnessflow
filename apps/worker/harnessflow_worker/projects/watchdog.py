"""Standalone supervisor: a killed worker cannot leave a coding process alive."""

import contextlib
import os
import signal
import subprocess
import sys
import time


def main() -> None:
    parent, seconds = int(sys.argv[1]), float(sys.argv[2])
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
    child = subprocess.Popen(
        sys.argv[3:],
        # Only this watchdog retains the repository flock until cleanup finishes.
        # Commands may start detached daemons; they must never inherit that lock.
        close_fds=True,
        start_new_session=True,
        preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask),
    )

    def stop(signum: int, _frame: object) -> None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()
        sys.exit(124 if signum == signal.SIGALRM else 128 + signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    deadline = time.monotonic() + seconds
    while child.poll() is None:
        if os.getppid() != parent or time.monotonic() >= deadline:
            stop(signal.SIGALRM, None)
        time.sleep(0.1)
    with contextlib.suppress(ProcessLookupError):
        os.killpg(child.pid, signal.SIGKILL)
    sys.exit(child.returncode)


if __name__ == "__main__":
    main()
