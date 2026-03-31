import json
import logging
import uuid
from datetime import datetime

from paperscout.state.database import add_eval_result

logger = logging.getLogger("evals")


def run_evals(result: dict, run_id: str | None = None) -> dict:
    """Run all Layer 1 deterministic evals on a pipeline result.

    Returns a summary dict with pass/fail counts and details.
    """
    if not run_id:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]

    logger.info("Running evals for run %s", run_id)

    checks = [
        *_search_evals(result),
        *_relevance_evals(result),
        *_extraction_evals(result),
        *_report_evals(result),
    ]

    passed = sum(1 for c in checks if c["passed"])
    failed = sum(1 for c in checks if not c["passed"])

    for check in checks:
        add_eval_result(run_id, check["name"], check["passed"], check["details"])
        status = "PASS" if check["passed"] else "FAIL"
        logger.info("  [%s] %s — %s", status, check["name"], check["details"])

    logger.info("Evals complete: %d passed, %d failed", passed, failed)
    return {"run_id": run_id, "passed": passed, "failed": failed, "checks": checks}


# --- Search evals ---

def _search_evals(result: dict) -> list[dict]:
    checks = []
    discovered = result.get("discovered_papers", [])

    # Check: at least one paper was found
    checks.append({
        "name": "search_returned_results",
        "passed": len(discovered) > 0,
        "details": f"{len(discovered)} papers discovered",
    })

    # Check: no duplicate IDs
    ids = [p["id"] for p in discovered]
    unique_ids = set(ids)
    has_dupes = len(ids) != len(unique_ids)
    checks.append({
        "name": "search_no_duplicates",
        "passed": not has_dupes,
        "details": f"{len(ids)} total, {len(unique_ids)} unique"
        + (f" — {len(ids) - len(unique_ids)} duplicates found" if has_dupes else ""),
    })

    # Check: all papers have required fields
    missing_fields = []
    for p in discovered:
        for field in ("id", "title", "abstract", "source", "url"):
            if not p.get(field):
                missing_fields.append(f"{p.get('id', '?')} missing {field}")
    checks.append({
        "name": "search_complete_fields",
        "passed": len(missing_fields) == 0,
        "details": f"{len(missing_fields)} missing fields" + (f": {missing_fields[:3]}" if missing_fields else ""),
    })

    return checks


# --- Relevance evals ---

def _relevance_evals(result: dict) -> list[dict]:
    checks = []
    discovered = result.get("discovered_papers", [])
    relevant = result.get("relevant_papers", [])

    # Only run relevance evals if we had papers to score
    if not discovered:
        return checks

    # Check: all scores are in valid range (1-10)
    scored = [p for p in discovered if p.get("relevance_score") is not None]
    out_of_range = [
        p["id"] for p in scored
        if not (1 <= p["relevance_score"] <= 10)
    ]
    checks.append({
        "name": "relevance_scores_in_range",
        "passed": len(out_of_range) == 0,
        "details": f"{len(scored)} scored, {len(out_of_range)} out of range [1-10]",
    })

    # Check: score distribution is not degenerate (not all the same score)
    if len(scored) >= 3:
        scores = [p["relevance_score"] for p in scored]
        all_same = len(set(scores)) == 1
        checks.append({
            "name": "relevance_score_variance",
            "passed": not all_same,
            "details": f"scores: min={min(scores)}, max={max(scores)}, unique={len(set(scores))}"
            if not all_same else f"all papers scored {scores[0]} — possible prompt issue",
        })

    # Check: every discovered paper got a score (no silent failures)
    unscored = [p["id"] for p in discovered if p.get("relevance_score") is None]
    checks.append({
        "name": "relevance_all_scored",
        "passed": len(unscored) == 0,
        "details": f"{len(scored)}/{len(discovered)} papers scored"
        + (f" — {len(unscored)} unscored" if unscored else ""),
    })

    # Check: filtering ratio is reasonable (between 5% and 95%)
    if scored:
        ratio = len(relevant) / len(scored)
        reasonable = 0.05 <= ratio <= 0.95
        checks.append({
            "name": "relevance_filter_ratio",
            "passed": reasonable,
            "details": f"{len(relevant)}/{len(scored)} passed ({ratio:.0%})"
            + (" — threshold may need tuning" if not reasonable else ""),
        })

    return checks


# --- Extraction evals ---

def _extraction_evals(result: dict) -> list[dict]:
    checks = []
    extracted = result.get("extracted_papers", [])

    if not extracted:
        return checks

    # Check: every extracted paper has at least one finding
    no_findings = [p["id"] for p in extracted if not p.get("key_findings")]
    checks.append({
        "name": "extraction_has_findings",
        "passed": len(no_findings) == 0,
        "details": f"{len(extracted) - len(no_findings)}/{len(extracted)} papers have findings"
        + (f" — {len(no_findings)} empty" if no_findings else ""),
    })

    # Check: findings are non-trivial (>10 chars each)
    trivial = []
    for p in extracted:
        for f in (p.get("key_findings") or []):
            if len(f.strip()) <= 10:
                trivial.append(f"{p['id']}: '{f[:20]}'")
    checks.append({
        "name": "extraction_findings_nontrivial",
        "passed": len(trivial) == 0,
        "details": f"{len(trivial)} trivial findings (<= 10 chars)" + (f": {trivial[:3]}" if trivial else ""),
    })

    # Check: no duplicate findings within a single paper
    papers_with_dupes = []
    for p in extracted:
        findings = p.get("key_findings") or []
        if len(findings) != len(set(findings)):
            papers_with_dupes.append(p["id"])
    checks.append({
        "name": "extraction_no_duplicate_findings",
        "passed": len(papers_with_dupes) == 0,
        "details": f"{len(papers_with_dupes)} papers have duplicate findings" if papers_with_dupes else "all findings unique",
    })

    return checks


# --- Report evals ---

def _report_evals(result: dict) -> list[dict]:
    checks = []
    html = result.get("report_html", "")
    extracted = result.get("extracted_papers", [])

    # Only run report evals if we had papers to report
    if not extracted:
        return checks

    # Check: report HTML is non-empty
    checks.append({
        "name": "report_html_generated",
        "passed": len(html) > 0,
        "details": f"report is {len(html)} chars" if html else "no report generated",
    })

    # Check: report contains all extracted paper titles
    if html:
        missing_titles = [p["title"] for p in extracted if p["title"] not in html]
        checks.append({
            "name": "report_contains_all_papers",
            "passed": len(missing_titles) == 0,
            "details": f"{len(extracted) - len(missing_titles)}/{len(extracted)} papers in report"
            + (f" — {len(missing_titles)} missing" if missing_titles else ""),
        })

    return checks
