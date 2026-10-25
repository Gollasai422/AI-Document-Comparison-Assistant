
import os
import re
import time
import hashlib
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL_NAME = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b"
)
if not isinstance(MODEL_NAME, str):
    MODEL_NAME = "openai/gpt-oss-120b"
MODEL_NAME = MODEL_NAME.strip() or "openai/gpt-oss-120b"

# Keep each request reasonably small for Groq's TPM limit.
MAX_DOCUMENT_CHARS = 5000
MAX_OUTPUT_TOKENS = 500
MIN_REQUEST_INTERVAL = 2
MAX_RETRIES = 2

_last_request_time = 0.0
_SUMMARY_CACHE = {}


def as_text(value):
    """Safely convert common values to text."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for key in ("text", "full_text", "content"):
            if isinstance(value.get(key), str):
                return value[key].strip()

        return "\n".join(
            f"{key}: {as_text(item)}"
            for key, item in value.items()
            if item is not None
        )

    if isinstance(value, list):
        return "\n".join(
            as_text(item) for item in value if item is not None
        ).strip()

    return str(value)


def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "")
    if not isinstance(api_key, str):
        api_key = ""
    api_key = api_key.strip()

    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError(
            "Groq API key is missing. Check your .env file."
        )

    return Groq(api_key=api_key)


def select_document_samples(document_text):
    """
    Select excerpts from throughout the document.
    This reduces request size but may omit details between excerpts.
    """

    text = as_text(document_text)

    if not text:
        raise ValueError(
            "No readable PDF text was received. "
            "Check whether the PDF contains selectable text."
        )

    if len(text) <= MAX_DOCUMENT_CHARS:
        return text

    # Sample evenly across the full extracted text.
    number_of_samples = 5
    sample_size = MAX_DOCUMENT_CHARS // number_of_samples
    max_start = max(0, len(text) - sample_size)
    samples = []

    for i in range(number_of_samples):
        start = int(
            max_start * i / (number_of_samples - 1)
        )
        excerpt = text[start:start + sample_size].strip()
        samples.append(
            f"[Excerpt {i + 1} from position {start}]\n{excerpt}"
        )

    return "\n\n".join(samples)


def call_groq_text(prompt):
    """Request plain text, without JSON formatting requirements."""

    global _last_request_time

    client = get_groq_client()
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            elapsed = time.time() - _last_request_time
            wait_time = MIN_REQUEST_INTERVAL - elapsed

            if wait_time > 0:
                time.sleep(wait_time)

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful document analyst. "
                            "Use only supplied evidence. Do not invent facts. "
                            "Answer in concise plain text with the exact "
                            "headings requested. Never output JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_completion_tokens=MAX_OUTPUT_TOKENS
            )

            _last_request_time = time.time()

            content = response.choices[0].message.content
            content = as_text(content)

            if not content:
                raise ValueError("The AI returned an empty response.")

            return content

        except Exception as exc:
            last_error = exc
            message = str(exc).lower()

            is_rate_limit = any(
                term in message
                for term in (
                    "rate_limit",
                    "tokens per minute",
                    "request too large",
                    "error code: 413",
                    "error code: 429"
                )
            )

            if attempt < MAX_RETRIES - 1:
                time.sleep(20 if is_rate_limit else 3)

    raise RuntimeError(
        f"Groq request failed after retries: {last_error}"
    ) from last_error


def parse_sections(response, headings):
    """Read plain-text sections without using JSON."""

    response = as_text(response)
    result = {}
    current_heading = None

    for line in response.splitlines():
        line = line.strip()

        if not line:
            continue

        cleaned = re.sub(r"^#+\s*", "", line)
        cleaned = re.sub(r"^\*\*", "", cleaned)
        cleaned = re.sub(r"\*\*$", "", cleaned)
        cleaned = cleaned.strip()

        matched_heading = None
        remainder = ""

        for heading in headings:
            pattern = (
                r"^" + re.escape(heading) +
                r"\s*:?\s*(.*)$"
            )
            match = re.match(pattern, cleaned, re.IGNORECASE)

            if match:
                matched_heading = heading
                remainder = match.group(1).strip()
                break

        if matched_heading:
            current_heading = matched_heading
            result.setdefault(current_heading, [])

            if remainder:
                result[current_heading].append(remainder)
        elif current_heading:
            result[current_heading].append(line)

    return {
        key: "\n".join(lines).strip()
        for key, lines in result.items()
    }


def extract_bullets(text):
    """Convert a section into display-friendly list items."""

    text = as_text(text)
    items = []

    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r"^[-*•]\s*", "", line)
        line = re.sub(r"^\d+[.)]\s*", "", line)

        if line:
            items.append(line)

    return items


def summarize_document(document_text, filename="Document"):
    """Summarize a document with one compact AI request."""

    text = as_text(document_text)
    cache_key = hashlib.sha256(
        (filename + "\n" + text).encode("utf-8")
    ).hexdigest()

    if cache_key in _SUMMARY_CACHE:
        return _SUMMARY_CACHE[cache_key].copy()

    sampled_text = select_document_samples(text)

    prompt = f"""
Summarize the PDF excerpts below. They may be samples from different
parts of a longer document, so do not assume they represent every page.

Document name: {filename}

Use these exact headings:

SUMMARY:
Give a concise but useful overview.

KEY POINTS:
- List the most important points.

IMPORTANT DETAILS:
- Preserve important names, numbers, dates, definitions and technical facts.

LIMITATIONS:
- State that only excerpts were analyzed if the document was sampled.

Do not invent facts. Use only the supplied text.

DOCUMENT EXCERPTS:
{sampled_text}
"""

    answer = call_groq_text(prompt)

    sections = parse_sections(
        answer,
        [
            "SUMMARY",
            "KEY POINTS",
            "IMPORTANT DETAILS",
            "LIMITATIONS"
        ]
    )

    result = {
        "filename": filename,
        "summary": sections.get("SUMMARY", "").strip() or answer,
        "key_points": extract_bullets(
            sections.get("KEY POINTS", "")
        ),
        "important_details": extract_bullets(
            sections.get("IMPORTANT DETAILS", "")
        ),
        "limitations": extract_bullets(
            sections.get("LIMITATIONS", "")
        ),
        "chunks_processed": 1,
        "sampled": len(text) > MAX_DOCUMENT_CHARS
    }

    _SUMMARY_CACHE[cache_key] = result
    return result.copy()


def compare_documents(
    document_a_text,
    document_b_text,
    summary_a=None,
    summary_b=None
):
    """Compare the two compact summaries with one AI request."""

    if summary_a is None:
        summary_a = summarize_document(
            document_a_text,
            "Document A"
        )

    if summary_b is None:
        summary_b = summarize_document(
            document_b_text,
            "Document B"
        )

    prompt = f"""
Compare the following two PDF summaries carefully.

Use these exact headings:

OVERVIEW:
Explain the main relationship between the documents.

SIMILARITIES:
- List supported similarities.

DIFFERENCES:
- List supported differences, including figures or claims when available.

KEY DETAILS:
- List important findings and identify Document A or Document B.

CONCLUSION:
Give a balanced conclusion.

LIMITATIONS:
- Explain what cannot be confirmed from the available summaries.

Do not invent facts. Missing information is not automatically a contradiction.
Remember that a summary may be based on sampled excerpts, not every page.

DOCUMENT A:
{as_text(summary_a.get("summary"))}

KEY POINTS FROM DOCUMENT A:
{as_text(summary_a.get("key_points"))}

IMPORTANT DETAILS FROM DOCUMENT A:
{as_text(summary_a.get("important_details"))}

DOCUMENT B:
{as_text(summary_b.get("summary"))}

KEY POINTS FROM DOCUMENT B:
{as_text(summary_b.get("key_points"))}

IMPORTANT DETAILS FROM DOCUMENT B:
{as_text(summary_b.get("important_details"))}
"""

    answer = call_groq_text(prompt)

    sections = parse_sections(
        answer,
        [
            "OVERVIEW",
            "SIMILARITIES",
            "DIFFERENCES",
            "KEY DETAILS",
            "CONCLUSION",
            "LIMITATIONS"
        ]
    )

    overview = sections.get("OVERVIEW", "").strip()

    if not overview:
        overview = answer

    return {
        "overview": overview,
        "similarities": extract_bullets(
            sections.get("SIMILARITIES", "")
        ),
        "differences": extract_bullets(
            sections.get("DIFFERENCES", "")
        ),
        "key_details": extract_bullets(
            sections.get("KEY DETAILS", "")
        ),
        "conclusion": sections.get("CONCLUSION", "").strip(),
        "limitations": extract_bullets(
            sections.get("LIMITATIONS", "")
        )
    }
