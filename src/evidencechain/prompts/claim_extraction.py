from evidencechain.models.factcheck import ClaimExtractionChunk

CLAIM_EXTRACTION_PROMPT_VERSION = "claim-extraction-v1"

CLAIM_EXTRACTION_SYSTEM_PROMPT = """You extract factual claims from YouTube transcript chunks.

Return only claims that can be checked against outside evidence.
Ignore opinions, jokes, sarcasm, filler, questions, vague statements, and predictions
without a measurable claim.
Preserve timestamps from the input chunk.
Use one category per claim:
scientific, historical, medical, political, financial, legal, technology, product.
Assign confidence from 0.0 to 1.0 for how likely the text is a concrete factual claim.
Return valid JSON matching the requested schema.
"""


def build_claim_extraction_prompt(chunk: ClaimExtractionChunk) -> str:
    return f"""Extract factual claims from this transcript chunk.

Chunk:
{{
  "position": {chunk.position},
  "start_seconds": {chunk.start_seconds},
  "end_seconds": {chunk.end_seconds},
  "text": {chunk.text!r}
}}

Output JSON shape:
{{
  "claims": [
    {{
      "text": "specific factual claim",
      "category": "scientific|historical|medical|political|financial|legal|technology|product",
      "confidence": 0.0,
      "start_seconds": {chunk.start_seconds},
      "end_seconds": {chunk.end_seconds}
    }}
  ]
}}
"""
