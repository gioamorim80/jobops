"""Resume text extraction for PDF and DOCX uploads.

The extracted text is PII: it is stored under RLS and sent only to the
onboarding Anthropic call — never logged.
"""

import io

import docx
from pypdf import PdfReader

# Resumes are short; cap defensively to bound token usage without silently
# losing meaningful content.
MAX_RESUME_CHARS = 60_000


def extract_resume_text(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif name.endswith(".docx"):
        document = docx.Document(io.BytesIO(data))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    else:
        raise ValueError("Unsupported file type. Upload a PDF or DOCX resume.")
    return text.strip()[:MAX_RESUME_CHARS]
