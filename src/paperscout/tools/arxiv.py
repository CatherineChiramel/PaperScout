import httpx
from xml.etree import ElementTree

ARXIV_API_URL = "https://export.arxiv.org/api/query"

# Namespace used in arXiv Atom XML responses
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _build_date_filter(since: str | None) -> str:
    """Convert a 'YYYY-MM' or 'YYYY-MM-DD' since string into an arXiv submittedDate range.

    arXiv expects: submittedDate:[YYYYMMDDHHmm TO YYYYMMDDHHmm]
    We use '*' for the end to mean 'up to now'.
    """
    if not since:
        return ""
    parts = since.split("-")
    year = parts[0]
    month = parts[1] if len(parts) >= 2 else "01"
    day = parts[2] if len(parts) >= 3 else "01"
    return f" AND submittedDate:[{year}{month}{day}0000 TO *]"


def search_arxiv(query: str, max_results: int = 20, since: str | None = None) -> list[dict]:
    """Search arXiv for papers matching a query.

    Returns a list of paper dicts with id, title, authors, abstract, url, pdf_url.
    If since is provided (e.g. '2025-01'), only returns papers submitted from that date onward.
    """
    search_query = f"all:{query}{_build_date_filter(since)}"

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    response = httpx.get(ARXIV_API_URL, params=params, timeout=30)
    response.raise_for_status()

    root = ElementTree.fromstring(response.text)
    papers = []

    for entry in root.findall(f"{ATOM_NS}entry"):
        # Extract arXiv ID from the entry URL (e.g., "http://arxiv.org/abs/2401.12345v1" -> "2401.12345")
        raw_id = entry.find(f"{ATOM_NS}id").text
        paper_id = raw_id.split("/abs/")[-1].split("v")[0]

        title = entry.find(f"{ATOM_NS}title").text.strip().replace("\n", " ")

        authors = [
            author.find(f"{ATOM_NS}name").text
            for author in entry.findall(f"{ATOM_NS}author")
        ]

        abstract = entry.find(f"{ATOM_NS}summary").text.strip().replace("\n", " ")

        # Find the PDF link among the entry's links
        pdf_url = None
        for link in entry.findall(f"{ATOM_NS}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break

        papers.append({
            "id": paper_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "source": "arxiv",
            "url": f"https://arxiv.org/abs/{paper_id}",
            "pdf_url": pdf_url,
        })

    return papers
