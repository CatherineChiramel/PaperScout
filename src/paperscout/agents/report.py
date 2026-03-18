from pathlib import Path

from jinja2 import Template

from paperscout.state.graph_state import PaperScoutState
from paperscout.state.database import add_report, mark_papers_reported
from paperscout.tools.email import send_email

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "report.html"


def report_node(state: PaperScoutState) -> dict:
    """Compile extracted papers into an HTML report and send via email."""
    papers = state["extracted_papers"]
    topics = ", ".join(state["topics"])
    recipient = state["email_recipient"]

    if not papers:
        print("No papers to report.")
        return {"report_html": "", "report_sent": False}

    # Render HTML report
    template = Template(TEMPLATE_PATH.read_text())
    html = template.render(
        papers=papers,
        paper_count=len(papers),
        topics=topics,
    )

    print(f"Report compiled: {len(papers)} papers")

    # Send email if recipient is configured
    if recipient:
        try:
            subject = f"[PaperScout] {len(papers)} papers on {topics}"
            send_email(recipient, subject, html)
            print(f"Report sent to {recipient}")

            # Log the report and update paper statuses
            add_report(len(papers), recipient)
            paper_ids = [p["id"] for p in papers]
            mark_papers_reported(paper_ids)

            return {"report_html": html, "report_sent": True}
        except Exception as e:
            print(f"Email failed: {e}")
            return {"report_html": html, "report_sent": False}
    else:
        print("No email recipient configured, skipping send.")
        return {"report_html": html, "report_sent": False}
