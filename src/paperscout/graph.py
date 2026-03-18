from langgraph.graph import StateGraph, END

from paperscout.state.graph_state import PaperScoutState
from paperscout.agents.search import search_node
from paperscout.agents.relevance import relevance_node
from paperscout.agents.extraction import extraction_node
from paperscout.agents.report import report_node


def should_continue_to_extraction(state: PaperScoutState) -> str:
    """Skip extraction and report if no relevant papers found."""
    if state["relevant_papers"]:
        return "extraction"
    return END


def build_graph() -> StateGraph:
    graph = StateGraph(PaperScoutState)

    # Add nodes
    graph.add_node("search", search_node)
    graph.add_node("relevance", relevance_node)
    graph.add_node("extraction", extraction_node)
    graph.add_node("report", report_node)

    # Define edges
    graph.set_entry_point("search")
    graph.add_edge("search", "relevance")
    graph.add_conditional_edges("relevance", should_continue_to_extraction)
    graph.add_edge("extraction", "report")
    graph.add_edge("report", END)

    return graph.compile()
