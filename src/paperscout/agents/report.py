import logging
from pathlib import Path

from jinja2 import Template

from paperscout.state.graph_state import PaperScoutState
from paperscout.state.database import add_report, mark_papers_reported
from paperscout.tools.email import send_email

logger = logging.getLogger("report")

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "report.html"


def report_node(state: PaperScoutState) -> dict:
    """Compile extracted papers into an HTML report and send via email."""
    papers = state["extracted_papers"]
    topics = ", ".join(state["topics"])
    recipient = state["email_recipient"]

    if not papers:
        logger.info("No papers to report.")
        return {"report_html": "", "report_sent": False}

    # Render HTML report
    template = Template(TEMPLATE_PATH.read_text())
    html = template.render(
        papers=papers,
        paper_count=len(papers),
        topics=topics,
    )

    logger.info("Report compiled: %d papers", len(papers))

    # Send email if recipient is configured
    if recipient:
        try:
            subject = f"[PaperScout] {len(papers)} papers on {topics}"
            send_email(recipient, subject, html)
            logger.info("Report sent to %s", recipient)

            # Log the report and update paper statuses
            add_report(len(papers), recipient)
            paper_ids = [p["id"] for p in papers]
            mark_papers_reported(paper_ids)

            return {"report_html": html, "report_sent": True}
        except Exception as e:
            logger.error("Email failed: %s", e)
            return {"report_html": html, "report_sent": False}
    else:
        logger.warning("No email recipient configured, skipping send.")
        return {"report_html": html, "report_sent": False}
