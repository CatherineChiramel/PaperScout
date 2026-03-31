import time

import httpx

S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

FIELDS = "paperId,title,authors,abstract,url,openAccessPdf,externalIds"

MAX_RETRIES = 3


def search_semantic_scholar(query: str, max_results: int = 20, since: str | None = None) -> list[dict]:
    """Search Semantic Scholar for papers matching a query.

    Returns a list of paper dicts with id, title, authors, abstract, url, pdf_url.
    If since is provided (e.g. '2025-01' or '2025-01-15'), only returns papers from that date onward.
    """
    params = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": FIELDS,
    }

    if since:
        # Semantic Scholar accepts "YYYY-MM-DD:" to mean "from this date onward"
        # Pad to full date if only YYYY-MM was given
        parts = since.split("-")
        if len(parts) == 2:
            since_date = f"{since}-01"
        else:
            since_date = since
        params["publicationDateOrYear"] = f"{since_date}:"

    # Semantic Scholar free tier has strict rate limits — retry with backoff
    for attempt in range(MAX_RETRIES):
        response = httpx.get(S2_API_URL, params=params, timeout=30)
        if response.status_code == 429:
            wait = 2 ** attempt
            print(f"Rate limited by Semantic Scholar, retrying in {wait}s...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        break
    else:
        raise RuntimeError("Semantic Scholar API rate limit exceeded after retries")

    data = response.json()
    papers = []

    for item in data.get("data", []):
        # Prefer arXiv ID if available, otherwise use Semantic Scholar ID
        external_ids = item.get("externalIds") or {}
        arxiv_id = external_ids.get("ArXiv")
        paper_id = arxiv_id if arxiv_id else item["paperId"]

        # Skip papers without abstracts — we need them for relevance scoring
        abstract = item.get("abstract")
        if not abstract:
            continue

        authors = [a["name"] for a in (item.get("authors") or [])]

        pdf_url = None
        open_access = item.get("openAccessPdf")
        if open_access:
            pdf_url = open_access.get("url")

        papers.append({
            "id": paper_id,
            "title": item.get("title", ""),
            "authors": authors,
            "abstract": abstract,
            "source": "semantic_scholar",
            "url": item.get("url", ""),
            "pdf_url": pdf_url,
        })

    return papers
