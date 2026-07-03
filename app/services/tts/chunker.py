class TextChunker:
    """Buffers streamed tokens into speakable text chunks for low-latency TTS."""

    _BOUNDARIES = {".", "!", "?", ",", ";", ":", "\n"}

    def __init__(self, *, min_chars: int, max_chars: int) -> None:
        self._min_chars = min_chars
        self._max_chars = max_chars
        self._buffer = ""

    def push(self, token: str) -> list[str]:
        self._buffer += token
        chunks: list[str] = []

        while self._buffer:
            if len(self._buffer) >= self._max_chars:
                split_at = self._find_boundary(self._buffer, self._max_chars)
                if split_at is None:
                    split_at = self._max_chars

                chunk = self._buffer[:split_at].strip()
                self._buffer = self._buffer[split_at:].lstrip()
                if chunk:
                    chunks.append(chunk)
                continue

            if len(self._buffer) < self._min_chars:
                break

            split_at = self._find_boundary(self._buffer, len(self._buffer))
            if split_at is None:
                break

            chunk = self._buffer[:split_at].strip()
            self._buffer = self._buffer[split_at:].lstrip()
            if chunk:
                chunks.append(chunk)

        return chunks

    def flush(self) -> str | None:
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining or None

    def _find_boundary(self, text: str, limit: int) -> int | None:
        for index in range(min(limit, len(text)) - 1, self._min_chars - 1, -1):
            if text[index] in self._BOUNDARIES:
                return index + 1
        return None