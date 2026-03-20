import json
import time

from paperscout.state.graph_state import PaperScoutState, Paper
from paperscout.state.database import update_paper_score
from paperscout.llm import get_llm

# Delay between API calls to stay within free tier rate limits (15 req/min)
API_DELAY_SECONDS = 5
MAX_RETRIES = 3

SCORING_PROMPT = """You are a research paper relevance scorer. Given a paper's title and abstract,
score its relevance to the research topics on a scale of 1-10.

Research topics: {topics}

Scoring guide:
- 9-10: Directly addresses one of the topics as a primary focus
- 7-8: Strongly related, covers key aspects of the topics
- 5-6: Somewhat related, touches on the topics but not the main focus
- 3-4: Loosely related, only tangential connection
- 1-2: Not relevant

Paper title: {title}
Paper abstract: {abstract}

Respond with ONLY a JSON object in this exact format:
{{"score": <number>, "reason": "<one sentence explanation>"}}"""


def relevance_node(state: PaperScoutState) -> dict:
    """Score each discovered paper for relevance using Gemini.

    Filters papers below the minimum relevance score.
    """
    papers = state["discovered_papers"]
    min_score = state["min_relevance_score"]
    topics = ", ".join(state["topics"])

    if not papers:
        print("No papers to score.")
        return {"relevant_papers": []}

    llm = get_llm(state["llm_provider"], state["llm_model"])

    relevant: list[Paper] = []

    for i, paper in enumerate(papers, 1):
        print(f"Scoring paper {i}/{len(papers)}: {paper['title'][:60]}...")

        prompt = SCORING_PROMPT.format(
            topics=topics,
            title=paper["title"],
            abstract=paper["abstract"],
        )

        score = 5.0
        reason = "Scoring failed"
        for attempt in range(MAX_RETRIES):
            try:
                response = llm.invoke(prompt)
                text = response.content.strip()
                # Handle markdown code blocks in response
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                result = json.loads(text)
                score = float(result["score"])
                reason = result.get("reason", "")
                break
            except Exception as e:
                if "429" in str(e) and attempt < MAX_RETRIES - 1:
                    wait = API_DELAY_SECONDS * (attempt + 2)
                    print(f"  Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"  Scoring failed: {e}, defaulting to 5")
                break

        time.sleep(API_DELAY_SECONDS)

        paper["relevance_score"] = score
        update_paper_score(paper["id"], score)
        print(f"  Score: {score}/10 — {reason}")

        if score >= min_score:
            relevant.append(paper)

    print(f"\n{len(relevant)}/{len(papers)} papers passed relevance threshold ({min_score})")
    return {"relevant_papers": relevant}
