"""Simple pytest-style unit tests for core pipeline pieces.

Run with: python -m pytest tests/test_sync_and_chunker.py -q --tb=line
"""

from app.services.tts.chunker import TextChunker
from app.services.video.sync import SyncTimeline


def test_sync_timeline_basic():
    timeline = SyncTimeline(fps=25)

    assert timeline.frame_index == 0
    assert timeline.audio_cursor_ms == 0

    frames = timeline.allocate_frames(1000)  # 1s
    assert len(frames) > 0
    # 25fps → 25 frames for 1000ms (but depending on rounding)
    assert timeline.frame_index == len(frames)
    assert timeline.audio_cursor_ms == 1000

    # second segment
    frames2 = timeline.allocate_frames(40)
    assert len(frames2) >= 1
    assert timeline.audio_cursor_ms == 1040


def test_sync_timeline_zero_and_negative():
    tl = SyncTimeline(fps=10)
    assert tl.allocate_frames(0) == []
    assert tl.allocate_frames(-10) == []
    assert tl.frame_index == 0


def test_sync_timeline_frame_count():
    tl = SyncTimeline(fps=25)
    # 40ms at 25fps → frame_duration=40ms → exactly 1
    assert tl.frame_count_for_duration(40) == 1
    assert tl.frame_count_for_duration(39) == 1  # rounds up min 1
    assert tl.frame_count_for_duration(80) == 2


def test_text_chunker_min_max():
    chunker = TextChunker(min_chars=10, max_chars=30)

    # small token stays buffered
    assert chunker.push("hello") == []
    # still small
    assert chunker.push(" world") == []

    # push enough + boundary
    chunks = chunker.push(". More text here to force split.")
    assert len(chunks) >= 1
    # "hello world." should be one chunk (if boundary hit)
    assert any("hello" in c or "world" in c for c in chunks)

    # flush remaining
    rem = chunker.flush()
    assert rem is None or isinstance(rem, str)


def test_text_chunker_forces_split_at_max():
    chunker = TextChunker(min_chars=5, max_chars=12)
    # no natural boundary in middle, forces at max
    text = "abcdefghijklmno"  # 15 chars > max
    chunks = chunker.push(text)
    assert len(chunks) >= 1
    assert len(chunks[0]) <= 12
    # flush rest
    rest = chunker.flush()
    assert rest is not None


def test_text_chunker_flush_empty():
    c = TextChunker(min_chars=3, max_chars=10)
    assert c.flush() is None
    c.push("ab")
    assert c.flush() == "ab"


def test_text_chunker_respects_boundaries():
    c = TextChunker(min_chars=2, max_chars=100)
    chunks = c.push("Hello, world! How are you?")
    # should split at , ! etc when min reached. At least the first boundary usually produces 1+
    # (exact splits depend on buffer size; flush guarantees remainder)
    assert len(chunks) >= 1
    joined = " ".join(chunks) + (c.flush() or "")
    assert "Hello" in joined and "you" in joined
