import subprocess


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
