from typing import TypedDict


class Paper(TypedDict):
    id: str
    title: str
    authors: list[str]
    abstract: str
    source: str
    url: str
    pdf_url: str | None
    relevance_score: float | None
    key_findings: list[str] | None


class PaperScoutState(TypedDict):
    # Input
    topics: list[str]
    max_results_per_query: int
    search_since: str
    min_relevance_score: float
    email_recipient: str
    llm_provider: str
    llm_model: str

    # Populated by search node
    discovered_papers: list[Paper]

    # Populated by relevance node
    relevant_papers: list[Paper]

    # Populated by extraction node
    extracted_papers: list[Paper]

    # Populated by report node
    report_html: str
    report_sent: bool
