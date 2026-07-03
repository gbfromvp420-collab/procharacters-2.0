class SyncTimeline:
    """Maps audio chunk durations to monotonic video presentation timestamps."""

    def __init__(self, fps: int) -> None:
        self._fps = fps
        self._frame_index = 0
        self._audio_cursor_ms = 0

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