import logging

from paperscout.state.graph_state import PaperScoutState, Paper
from paperscout.tools.arxiv import search_arxiv
from paperscout.tools.semantic_scholar import search_semantic_scholar
from paperscout.state.database import add_paper, add_search, paper_already_processed

logger = logging.getLogger("search")


def search_node(state: PaperScoutState) -> dict:
    """Search arXiv and Semantic Scholar for papers on each topic.

    Deduplicates by paper ID and saves results to the database.
    """
    topics = state["topics"]
    max_results = state["max_results_per_query"]
    since = state.get("search_since")
    seen_ids: set[str] = set()
    all_papers: list[Paper] = []

    for topic in topics:
        logger.info("Searching arXiv for: %s", topic)
        try:
            arxiv_papers = search_arxiv(topic, max_results=max_results, since=since)
            add_search(topic, "arxiv", len(arxiv_papers))
            for p in arxiv_papers:
                if p["id"] not in seen_ids and not paper_already_processed(p["id"]):
                    seen_ids.add(p["id"])
                    paper: Paper = {**p, "relevance_score": None, "key_findings": None}
                    all_papers.append(paper)
                    add_paper(
                        paper_id=p["id"],
                        title=p["title"],
                        authors=p["authors"],
                        abstract=p["abstract"],
                        source=p["source"],
                        url=p["url"],
                        pdf_url=p.get("pdf_url"),
                    )
        except Exception as e:
            logger.error("arXiv search failed: %s", e)

        # print(f"Searching Semantic Scholar for: {topic}")
        # try:
        #     s2_papers = search_semantic_scholar(topic, max_results=max_results, since=since)
        #     add_search(topic, "semantic_scholar", len(s2_papers))
        #     for p in s2_papers:
        #         if p["id"] not in seen_ids and not paper_already_processed(p["id"]):
        #             seen_ids.add(p["id"])
        #             paper: Paper = {**p, "relevance_score": None, "key_findings": None}
        #             all_papers.append(paper)
        #             add_paper(
        #                 paper_id=p["id"],
        #                 title=p["title"],
        #                 authors=p["authors"],
        #                 abstract=p["abstract"],
        #                 source=p["source"],
        #                 url=p["url"],
        #                 pdf_url=p.get("pdf_url"),
        #             )
        # except Exception as e:
        #     print(f"  Semantic Scholar search failed: {e}")

    logger.info("Total unique papers discovered: %d", len(all_papers))
    return {"discovered_papers": all_papers}
