# Transcript API

Base path: `/api/v1`

## Create From YouTube URL

`POST /transcripts/from-url`

Fetches YouTube metadata through `yt-dlp`, selects a manual or automatic caption track, downloads the transcript, normalizes segments, stores the transcript in SQLite, and creates chunks.

Request:

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "language": "en"
}
```

Success: `200 OK`

Returns transcript metadata, segments, and chunks.

Errors:

| Status | Meaning |
| --- | --- |
| `404` | No transcript was available for the video |
| `502` | YouTube metadata or caption retrieval failed after retries |

## Upload Transcript Fallback

`POST /transcripts/upload`

Multipart form upload for transcript files when YouTube captions are missing or unusable.

Supported file types:

| Extension | Notes |
| --- | --- |
| `.txt` | Stored as one untimed segment at `0` seconds |
| `.srt` | Preserves SRT timestamps |
| `.vtt` | Preserves WebVTT timestamps and strips caption tags |
| `.json` | Supports a list of segments, `{ "segments": [...] }`, or YouTube `json3` events |

Form fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `file` | Yes | Transcript file |
| `youtube_url` | No | Related YouTube URL |
| `title` | No | Uploaded transcript title |
| `video_id` | No | Related video ID |
| `language` | No | Transcript language, defaults to `en` |

Example:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/transcripts/upload `
  -Form @{
    file = Get-Item .\sample.vtt
    youtube_url = "https://www.youtube.com/watch?v=VIDEO_ID"
    title = "Sample"
    video_id = "VIDEO_ID"
    language = "en"
  }
```

Errors:

| Status | Meaning |
| --- | --- |
| `400` | Unsupported extension, invalid encoding, or invalid transcript body |

## Get Transcript

`GET /transcripts/{transcript_id}`

Returns the stored transcript, including metadata, normalized segments, and chunks.

Error:

| Status | Meaning |
| --- | --- |
| `404` | Transcript ID was not found |

## Get Chunks

`GET /transcripts/{transcript_id}/chunks`

Returns only chunk data for the transcript.

Chunk fields:

| Field | Purpose |
| --- | --- |
| `position` | Zero based chunk order |
| `start_seconds` | First segment timestamp in the chunk |
| `end_seconds` | Last segment timestamp in the chunk |
| `text` | Normalized chunk text |
| `segment_start_index` | First included source segment |
| `segment_end_index` | Last included source segment |

## JSON Transcript Format

Generic JSON upload:

```json
{
  "segments": [
    {
      "start": 1.0,
      "duration": 2.5,
      "text": "Transcript text."
    }
  ]
}
```

Also accepted:

```json
[
  {
    "start_seconds": 1.0,
    "end_seconds": 3.5,
    "text": "Transcript text."
  }
]
```

Claim extraction is intentionally not part of these endpoints.
