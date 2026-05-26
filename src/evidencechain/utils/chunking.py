from evidencechain.models.transcript import TranscriptChunk, TranscriptSegment


def chunk_transcript(
    segments: list[TranscriptSegment],
    max_chars: int,
    overlap_segments: int = 0,
) -> list[TranscriptChunk]:
    if max_chars < 1:
        raise ValueError("max_chars must be greater than zero")
    if overlap_segments < 0:
        raise ValueError("overlap_segments must be greater than or equal to zero")
    if not segments:
        return []

    chunks: list[TranscriptChunk] = []
    start_index = 0

    while start_index < len(segments):
        end_index = start_index
        chunk_segments: list[TranscriptSegment] = []
        chunk_length = 0

        while end_index < len(segments):
            candidate = segments[end_index]
            candidate_length = len(candidate.text) + (1 if chunk_segments else 0)
            if chunk_segments and chunk_length + candidate_length > max_chars:
                break
            chunk_segments.append(candidate)
            chunk_length += candidate_length
            end_index += 1

        first = chunk_segments[0]
        last = chunk_segments[-1]
        chunks.append(
            TranscriptChunk(
                position=len(chunks),
                start_seconds=first.start_seconds,
                end_seconds=last.end_seconds,
                text=" ".join(segment.text for segment in chunk_segments),
                segment_start_index=start_index,
                segment_end_index=end_index - 1,
            )
        )

        if end_index >= len(segments):
            break
        start_index = max(end_index - overlap_segments, start_index + 1)

    return chunks
