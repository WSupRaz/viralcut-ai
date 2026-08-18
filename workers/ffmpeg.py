import re
import subprocess
import threading
from collections import deque
from collections.abc import Callable


class FFmpegError(RuntimeError):
    """An ffmpeg/ffprobe invocation failed. Carries the stderr tail so job
    errors tell the user what actually went wrong instead of a bare
    CalledProcessError's return code."""


def run_ffmpeg(args: list[str], label: str = "ffmpeg") -> subprocess.CompletedProcess:
    """Run an ffmpeg/ffprobe command with output captured. On non-zero exit,
    raise FFmpegError with a trimmed stderr tail -- the raw CalledProcessError
    message is just an exit code and a command line, useless for debugging."""
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if len(detail) > 1500:
            detail = detail[-1500:]
        raise FFmpegError(
            f"{label} failed (exit {exc.returncode}): {detail}"
        ) from exc


_OUT_TIME_US_RE = re.compile(rb"out_time_us=(\d+)")


def run_ffmpeg_streaming_progress(
    args: list[str],
    duration_seconds: float | None,
    on_progress: Callable[[float], None],
    label: str = "ffmpeg",
) -> None:
    """Run ffmpeg, reporting completion fraction (0.0-1.0) as it encodes.

    A long transcode that only writes progress *before* it starts is
    indistinguishable from a transcode whose process was killed: the job row
    sits at the same number either way, with no way to tell "still working"
    from "died 20 minutes ago". `-progress pipe:1` makes ffmpeg emit machine-
    readable key=value blocks as it goes, so the job can advance while the
    encode runs.

    stderr is drained on a thread and kept as a bounded tail: without a reader
    a chatty ffmpeg can fill the pipe buffer and deadlock, and the tail is what
    makes a failure diagnosable.
    """
    # -hide_banner: the build-config banner is ~30 lines and would otherwise
    # crowd the real error out of the bounded stderr tail kept below.
    proc = subprocess.Popen(
        [*args, "-hide_banner", "-progress", "pipe:1", "-nostats"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stderr_tail: deque[bytes] = deque(maxlen=40)

    def drain_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_tail.append(line)

    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()

    assert proc.stdout is not None
    for line in proc.stdout:
        match = _OUT_TIME_US_RE.search(line)
        if not match or not duration_seconds or duration_seconds <= 0:
            continue
        encoded_seconds = int(match.group(1)) / 1_000_000
        on_progress(max(0.0, min(1.0, encoded_seconds / duration_seconds)))

    proc.wait()
    stderr_thread.join(timeout=5)

    if proc.returncode != 0:
        detail = b"".join(stderr_tail).decode("utf-8", "replace").strip()
        if len(detail) > 1500:
            detail = detail[-1500:]
        raise FFmpegError(f"{label} failed (exit {proc.returncode}): {detail}")


def probe_duration_seconds(path: str) -> float:
    """Media duration in seconds via ffprobe (streams; never loads the file
    into memory)."""
    result = run_ffmpeg(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        label="ffprobe",
    )
    return float(result.stdout.strip())
