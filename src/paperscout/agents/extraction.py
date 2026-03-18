import json
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from paperscout.state.graph_state import PaperScoutState, Paper
from paperscout.state.database import update_paper_findings
from paperscout.tools.pdf import download_and_extract

load_dotenv()

EXTRACTION_PROMPT = """You are a research paper analyst. Given the text of a research paper,
extract the 3-5 most important key findings or contributions.

Each finding should be a concise, self-contained sentence that captures
a specific result, method, or insight from the paper.

Paper title: {title}
Paper text (first pages):
{text}

Respond with ONLY a JSON array of strings, e.g.:
["Finding 1", "Finding 2", "Finding 3"]"""


def extraction_node(state: PaperScoutState) -> dict:
    """Download PDFs and extract key findings using Gemini.

    Skips papers without a PDF URL.
    """
    papers = state["relevant_papers"]

    if not papers:
        print("No relevant papers to extract.")
        return {"extracted_papers": []}

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.environ["GOOGLE_API_KEY"],
    )

    extracted: list[Paper] = []

    for i, paper in enumerate(papers, 1):
        print(f"Extracting paper {i}/{len(papers)}: {paper['title'][:60]}...")

        if not paper.get("pdf_url"):
            print("  No PDF URL, skipping extraction.")
            paper["key_findings"] = ["PDF not available for extraction."]
            extracted.append(paper)
            continue

        try:
            text = download_and_extract(paper["pdf_url"], max_pages=10)
            # Truncate to ~8000 chars to stay within token limits
            text = text[:8000]
        except Exception as e:
            print(f"  PDF download/extract failed: {e}")
            paper["key_findings"] = ["PDF extraction failed."]
            extracted.append(paper)
            continue

        try:
            prompt = EXTRACTION_PROMPT.format(title=paper["title"], text=text)
            response = llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            findings = json.loads(content)
        except Exception as e:
            print(f"  LLM extraction failed: {e}")
            findings = ["Extraction failed — see paper directly."]

        paper["key_findings"] = findings
        update_paper_findings(paper["id"], findings)
        print(f"  Extracted {len(findings)} findings")
        extracted.append(paper)

    print(f"\nExtracted findings from {len(extracted)} papers")
    return {"extracted_papers": extracted}
