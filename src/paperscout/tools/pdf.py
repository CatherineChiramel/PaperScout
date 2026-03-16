import tempfile
from pathlib import Path

import httpx
import pymupdf


def download_pdf(pdf_url: str) -> Path:
    """Download a PDF from a URL and save to a temp file.

    Returns the path to the downloaded file.
    """
    response = httpx.get(pdf_url, timeout=60, follow_redirects=True)
    response.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(response.content)
    tmp.close()
    return Path(tmp.name)


def extract_text(pdf_path: Path, max_pages: int = 20) -> str:
    """Extract text from a PDF file.

    Reads up to max_pages pages to keep processing reasonable.
    Returns the extracted text.
    """
    doc = pymupdf.open(str(pdf_path))
    pages_to_read = min(len(doc), max_pages)
    text = ""
    for i in range(pages_to_read):
        text += doc[i].get_text()
    doc.close()
    return text


def download_and_extract(pdf_url: str, max_pages: int = 20) -> str:
    """Download a PDF and extract its text in one step."""
    pdf_path = download_pdf(pdf_url)
    try:
        return extract_text(pdf_path, max_pages)
    finally:
        pdf_path.unlink(missing_ok=True)
