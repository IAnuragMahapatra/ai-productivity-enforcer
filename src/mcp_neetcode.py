import asyncio
import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

# --- Server and File Setup ---
mcp = FastMCP("NeetCode Progress Tracker")
BASE_DIR = Path(__file__).parent.parent
NEETCODE_FILE = BASE_DIR / "data" / "neetcode_progress.json"

# --- Helper Functions for Data Handling ---


def _load_data() -> Dict[str, Any]:
    """Loads NeetCode data. Initializes new summary fields if they don't exist."""
    default_summary = {
        "total_problems": 0,
        "problems_solved": 0,
        "progress_percentage": 0.0,
        "average_reattempt_count": 0.0,
        "all_solved_ids": [],
        "last_3_solved_ids": [],
        "last_5_reattempted_ids": [],
    }
    try:
        if NEETCODE_FILE.exists() and NEETCODE_FILE.stat().st_size > 0:
            with open(NEETCODE_FILE, "r") as f:
                data = json.load(f)
                if "summary" not in data:
                    data["summary"] = {}

                # For backward compatibility with 'average_solve_count'
                if "average_solve_count" in data["summary"]:
                    del data["summary"]["average_solve_count"]

                for key, value in default_summary.items():
                    if key not in data["summary"]:
                        data["summary"][key] = value

                # Always run an update on load to ensure data integrity
                _update_summary(data)
                return data
    except (json.JSONDecodeError, FileNotFoundError):
        pass

    default_data = {"summary": default_summary, "problems": []}
    if not NEETCODE_FILE.exists():
        with open(NEETCODE_FILE, "w") as f:
            json.dump(default_data, f, indent=2)
    return default_data


def _save_data(data: Dict[str, Any]):
    """Recalculates summary and saves the data back to the JSON file."""
    _update_summary(data)
    with open(NEETCODE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _update_summary(data: Dict[str, Any]):
    """Recalculates all summary metrics based on the current state of problems."""
    problems = data.get("problems", [])
    total_problems = len(problems)
    solved_problems = [p for p in problems if p.get("status") == "solved"]

    data["summary"]["total_problems"] = total_problems
    data["summary"]["problems_solved"] = len(solved_problems)
    data["summary"]["progress_percentage"] = round(
        (len(solved_problems) / total_problems * 100) if total_problems > 0 else 0, 2
    )
    data["summary"]["all_solved_ids"] = [p["id"] for p in solved_problems]

    # Only calculate average on problems that have actually been reattempted.
    reattempted_problems = [p for p in solved_problems if p.get("solve_count", 0) > 1]
    if reattempted_problems:
        total_reattempts = sum(p.get("solve_count", 0) for p in reattempted_problems)
        data["summary"]["average_reattempt_count"] = round(
            total_reattempts / len(reattempted_problems), 2
        )
    else:
        data["summary"]["average_reattempt_count"] = 0.0  # No reattempts yet

    solved_by_date = sorted(
        solved_problems,
        key=lambda p: p.get("last_solved_date") or "1970-01-01",
        reverse=True,
    )
    data["summary"]["last_3_solved_ids"] = [p["id"] for p in solved_by_date[:3]]


# --- MCP Tools ---


@mcp.tool()
def get_daily_problems(num_new: int = 2, num_reattempt: int = 1) -> str:
    """
    Suggests a configurable number of new and reattempt problems for daily practice.

    Args:
        num_new (int): Number of new problems to suggest (default 2).
        num_reattempt (int): Number of reattempt problems to suggest (default 1).

    Returns:
        str: JSON object with keys:
            - 'new_problems': List of new problem dicts (status 'new'), prioritizing topic diversity (avoiding topics from last 3 solved problems), lowest IDs first. If not enough, falls back to any new problems.
            - 'reattempt_problems': List of previously solved problem dicts (not in last 3 solved or last 5 reattempted), prioritizing those with solve_count == 1 or <= average_reattempt_count, and those solved longest ago. If not enough, falls back to oldest-solved valid problems.

    This tool is designed for agentic LLMs to generate daily practice sets with topic diversity and balanced reattempts.
    """
    data = _load_data()
    summary = data["summary"]
    problems = data["problems"]

    new_suggestions = []
    solved_ids = set(summary.get("all_solved_ids", []))
    last_solved_topics = {
        p["topic"] for p in problems if p["id"] in summary.get("last_3_solved_ids", [])
    }
    candidate_pool = [p for p in problems if p["id"] not in solved_ids]
    priority_candidates = [
        p for p in candidate_pool if p["topic"] not in last_solved_topics
    ]
    new_suggestions.extend(priority_candidates[:num_new])
    if len(new_suggestions) < num_new:
        remaining_candidates = [p for p in candidate_pool if p not in new_suggestions]
        new_suggestions.extend(remaining_candidates[: num_new - len(new_suggestions)])

    reattempt_suggestions = []
    forbidden_ids = set(summary.get("last_3_solved_ids", [])) | set(
        summary.get("last_5_reattempted_ids", [])
    )
    avg_reattempt_count = summary.get("average_reattempt_count", 0.0)
    reattempt_candidates = [
        p for p in problems if p["id"] in solved_ids and p["id"] not in forbidden_ids
    ]
    priority_pool = [
        p
        for p in reattempt_candidates
        if p.get("solve_count", 1) == 1
        or p.get("solve_count", 1) <= avg_reattempt_count
    ]
    final_pool = priority_pool if priority_pool else reattempt_candidates
    if final_pool:
        final_pool.sort(key=lambda p: p.get("last_solved_date") or "1970-01-01")
        reattempt_suggestions.extend(final_pool[:num_reattempt])

    return json.dumps(
        {"new_problems": new_suggestions, "reattempt_problems": reattempt_suggestions},
        indent=2,
    )


@mcp.tool()
def update_problem(name: str, notes: Optional[str] = None) -> str:
    """
    Marks a problem as 'solved' and updates its notes. This is the primary
    way to log progress. It automatically handles all summary fields.

    Args:
        name (str): The exact, case-insensitive name of the problem to update.
        notes (Optional[str], optional): How the problem was solved.

    Returns:
        str: A confirmation message indicating success or an error.
    """
    data = _load_data()
    problem_to_update = next(
        (p for p in data["problems"] if p.get("name", "").lower() == name.lower()), None
    )

    if not problem_to_update:
        return f"Error: Problem with name '{name}' not found."

    is_reattempt = problem_to_update.get("status") == "solved"

    problem_to_update["status"] = "solved"
    problem_to_update["solve_count"] = problem_to_update.get("solve_count", 0) + 1
    problem_to_update["last_solved_date"] = datetime.date.today().isoformat()
    if notes is not None:
        problem_to_update["notes"] = notes

    if is_reattempt:
        reattempt_list = data["summary"].get("last_5_reattempted_ids", [])
        if problem_to_update["id"] in reattempt_list:
            reattempt_list.remove(problem_to_update["id"])
        new_reattempt_list = [problem_to_update["id"]] + reattempt_list
        data["summary"]["last_5_reattempted_ids"] = new_reattempt_list[:5]

    _save_data(data)

    action = "reattempted" if is_reattempt else "solved for the first time"
    return f"Successfully logged '{name}' as {action}. Progress summary updated."


@mcp.tool()
def get_progress_summary() -> str:
    """Reads and returns the summary of NeetCode progress."""
    data = _load_data()
    return json.dumps(data.get("summary", {}), indent=2)


@mcp.tool()
def find_problem_by_id(problem_id: int) -> str:
    """Finds a specific problem by its unique integer ID."""
    data = _load_data()
    problem = next((p for p in data["problems"] if p.get("id") == problem_id), None)
    return (
        json.dumps(problem, indent=2)
        if problem
        else json.dumps({"error": f"Problem with ID '{problem_id}' not found."})
    )


# --- To run the server directly ---
if __name__ == "__main__":
    print("Starting NeetCode Progress Tracker MCP Server...")
    print("\n--- Available Tools ---")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"- {tool.name}")
    print("\nConnect your multi-tool agent to use this server.")
    mcp.run()
