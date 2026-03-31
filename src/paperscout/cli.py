import argparse
import logging
from pathlib import Path
import os

import yaml
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from paperscout.state.database import init_db, get_all_papers
from paperscout.graph import build_graph

CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


def load_config(config_path: Path = CONFIG_PATH) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def run(config_path: Path = CONFIG_PATH):
    """Run the full PaperScout pipeline once."""
    load_dotenv()

    # Start Phoenix tracing — dashboard at http://localhost:6006
    import phoenix as px
    from openinference.instrumentation.langchain import LangChainInstrumentor
    px.launch_app()
    LangChainInstrumentor().instrument()

    config = load_config(config_path)
    init_db()

    initial_state = {
        "topics": config["topics"],
        "max_results_per_query": config["search"]["max_results_per_query"],
        "search_since": config["search"].get("since", "2025-01"),
        "min_relevance_score": config["relevance"]["min_score"],
        "email_recipient": os.getenv('GMAIL_ADDRESS'),
        "llm_provider": config["llm"]["provider"],
        "llm_model": config["llm"]["model"],
        "discovered_papers": [],
        "relevant_papers": [],
        "extracted_papers": [],
        "report_html": "",
        "report_sent": False,
    }

    print("=== PaperScout Starting ===\n")
    graph = build_graph()
    result = graph.invoke(
        initial_state,
        config={
            "run_name": "PaperScout Pipeline",
            "metadata": {
                "topics": ", ".join(config["topics"]),
                "llm_provider": config["llm"]["provider"],
                "llm_model": config["llm"]["model"],
                "search_since": config["search"].get("since", "2025-01"),
            },
        },
    )

    print("\n=== PaperScout Complete ===")
    print(f"Papers discovered: {len(result['discovered_papers'])}")
    print(f"Papers relevant:   {len(result['relevant_papers'])}")
    print(f"Papers extracted:  {len(result['extracted_papers'])}")
    print(f"Report sent:       {result['report_sent']}")

    if result["report_html"] and not result["report_sent"]:
        # Save report locally if email wasn't sent
        report_path = Path("report.html")
        report_path.write_text(result["report_html"])
        print(f"Report saved to:   {report_path}")


def status():
    """Show current database status."""
    init_db()
    papers = get_all_papers()

    if not papers:
        print("No papers in database yet. Run `paperscout run` first.")
        return

    counts = {}
    for p in papers:
        counts[p["status"]] = counts.get(p["status"], 0) + 1

    print(f"Total papers: {len(papers)}")
    for s, c in counts.items():
        print(f"  {s}: {c}")


def main():
    parser = argparse.ArgumentParser(description="PaperScout — Agentic Research Assistant")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="Run the full pipeline once")
    subparsers.add_parser("status", help="Show database status")

    args = parser.parse_args()

    if args.command == "run":
        run()
    elif args.command == "status":
        status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
