"""Bound native WebRTC socket growth without persisting runtime state."""

from pathlib import Path


DEFAULT_SOCKET_RECYCLE_THRESHOLD = 256


def count_open_socket_descriptors(
    descriptor_directory: Path = Path("/proc/self/fd"),
) -> int | None:
    """Return the process socket count, or None when procfs is unavailable."""

    try:
        descriptors = tuple(descriptor_directory.iterdir())
    except OSError:
        return None

    count = 0
    for descriptor in descriptors:
        try:
            target = descriptor.readlink()
        except OSError:
            continue
        if str(target).startswith("socket:"):
            count += 1
    return count


def should_recycle_socket_connection(
    socket_count: int | None,
    *,
    reconnect_pending: bool,
    threshold: int = DEFAULT_SOCKET_RECYCLE_THRESHOLD,
) -> bool:
    if threshold < 1:
        raise ValueError("Socket recycle threshold must be positive")
    if reconnect_pending:
        return True
    return socket_count is not None and socket_count >= threshold
