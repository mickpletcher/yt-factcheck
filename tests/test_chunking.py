from evidencechain.models.transcript import TranscriptSegment
from evidencechain.utils.chunking import chunk_transcript


def test_chunk_transcript_preserves_timestamps_and_overlap() -> None:
    segments = [
        TranscriptSegment(start_seconds=0, end_seconds=2, text="one two"),
        TranscriptSegment(start_seconds=2, end_seconds=4, text="three four"),
        TranscriptSegment(start_seconds=4, end_seconds=6, text="five six"),
    ]

    chunks = chunk_transcript(segments, max_chars=19, overlap_segments=1)

    assert len(chunks) == 2
    assert chunks[0].text == "one two three four"
    assert chunks[0].start_seconds == 0
    assert chunks[0].end_seconds == 4
    assert chunks[1].text == "three four five six"
    assert chunks[1].start_seconds == 2
    assert chunks[1].segment_start_index == 1
