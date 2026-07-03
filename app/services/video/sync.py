class SyncTimeline:
    """Maps audio chunk durations to monotonic video presentation timestamps.

    Supports initialization with start offsets for continuous PTS across
    multi-turn / resume performs on the same WebRTC session+bridge.
    (Defaults preserve backward compat for standalone /video/sync etc.)
    """

    def __init__(
        self, fps: int, *, start_audio_ms: int = 0, start_frame_index: int = 0
    ) -> None:
        self._fps = fps
        self._frame_index = start_frame_index
        self._audio_cursor_ms = start_audio_ms

    @property
    def audio_cursor_ms(self) -> int:
        return self._audio_cursor_ms

    @property
    def frame_index(self) -> int:
        return self._frame_index

    def frame_count_for_duration(self, duration_ms: int) -> int:
        if duration_ms <= 0:
            return 0
        frame_duration_ms = 1000 / self._fps
        return max(1, int(round(duration_ms / frame_duration_ms)))

    def allocate_frames(self, duration_ms: int) -> list[tuple[int, int]]:
        """Return (frame_index, pts_ms) pairs for the next audio segment."""
        start_ms = self._audio_cursor_ms
        count = self.frame_count_for_duration(duration_ms)
        frame_duration_ms = 1000 / self._fps

        start_frame_index = self._frame_index
        frames: list[tuple[int, int]] = []
        for offset in range(count):
            frames.append(
                (start_frame_index + offset, start_ms + int(offset * frame_duration_ms))
            )

        self._commit_segment(duration_ms, count)
        return frames

    def commit_segment(self, duration_ms: int, frame_count: int) -> None:
        self._commit_segment(duration_ms, frame_count)

    def _commit_segment(self, duration_ms: int, frame_count: int) -> None:
        self._audio_cursor_ms += duration_ms
        self._frame_index += frame_count