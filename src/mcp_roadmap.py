import asyncio
import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

# --- Server and File Setup ---
mcp = FastMCP("Roadmap Tracker")
BASE_DIR = Path(__file__).parent.parent / "data"
ROADMAP_FILE = BASE_DIR / "roadmap.json"
TRACKER_FILE = BASE_DIR / "roadmap_tracker.json"

# --- Helper Functions for Data Handling ---


def _load_roadmap_data() -> Dict[str, Any]:
    """Loads the static roadmap plan data."""
    try:
        with open(ROADMAP_FILE, "r") as f:
            data = json.load(f)
            if "name" not in data:
                data["name"] = "Unnamed Roadmap"
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"name": "Unnamed Roadmap", "phases": [], "daily_tasks": {}}


def _load_tracker_data() -> Dict[str, Any]:
    """
    Loads the dynamic progress tracker data from the tracker file. If the file does not exist or is empty/invalid,
    creates a new default tracker with name copied from roadmap.json, start_date=None, current_day=1, status='not_started', and empty history.
    Returns:
        dict: The current tracker data.
    """
    if TRACKER_FILE.exists() and TRACKER_FILE.stat().st_size > 0:
        try:
            with open(TRACKER_FILE, "r") as f:
                data = json.load(f)
                if "name" not in data:
                    roadmap = _load_roadmap_data()
                    data["name"] = roadmap.get("name", "Unnamed Roadmap")
                return data
        except json.JSONDecodeError:
            pass
    roadmap = _load_roadmap_data()
    default_tracker = {
        "name": roadmap.get("name", "Unnamed Roadmap"),
        "start_date": None,
        "current_day": 1,
        "status": "not_started",
        "history": {},
    }
    _save_tracker_data(default_tracker)
    return default_tracker


def _save_tracker_data(data: Dict[str, Any]):
    """
    Saves the given tracker data dictionary to the tracker file as JSON.
    Args:
        data (dict): The tracker data to save.
    """
    with open(TRACKER_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _get_phase_for_day(roadmap_data: Dict, day_number: int) -> Optional[Dict]:
    """
    Finds and returns the phase dictionary for the given day number from the roadmap data.
    Args:
        roadmap_data (dict): The loaded roadmap data.
        day_number (int): The day number to look up.
    Returns:
        dict or None: The phase dict if found, else None.
    """
    for phase in roadmap_data.get("phases", []):
        start, end = phase.get("days", [0, 0])
        if start <= day_number <= end:
            return phase
    return None


# --- MCP Tools ---


@mcp.tool()
def start_roadmap(start_date: Optional[str] = None) -> str:
    """
    Start or reset the roadmap progress.

    This tool initializes or resets the roadmap tracker. It sets the start date (either provided in 'YYYY-MM-DD' format or defaults to today's date), resets the current day to 1, status to 'in_progress', and clears the completion history. Use this tool to begin a new roadmap journey or restart progress from the beginning.

    Args:
        start_date (Optional[str]): The start date in 'YYYY-MM-DD' format. If not provided, uses today's date.

    Returns:
        str: Confirmation message with the set start date and current day.
    """
    tracker = _load_tracker_data()
    roadmap = _load_roadmap_data()
    tracker["name"] = roadmap.get("name", "Unnamed Roadmap")
    if start_date:
        try:
            datetime.datetime.strptime(start_date, "%Y-%m-%d")
            tracker["start_date"] = start_date
        except ValueError:
            return "Error: Invalid date format. Please use YYYY-MM-DD."
    else:
        tracker["start_date"] = datetime.date.today().isoformat()
    tracker["current_day"] = 1
    tracker["status"] = "in_progress"
    tracker["history"] = {}
    _save_tracker_data(tracker)
    return (
        f"Roadmap started! Start date set to {tracker['start_date']}. You are on Day 1."
    )


@mcp.tool()
def get_roadmap_status() -> str:
    """
    Get a summary of the current roadmap progress.

    This tool returns a high-level JSON summary of the user's current roadmap status, including the roadmap name, current day, current phase, start date, completion percentage, and overall status (not_started, in_progress, or completed). Use this tool to check progress or display a dashboard overview.

    Returns:
        str: JSON string with keys: name, status, current_day, current_phase, start_date, progress_percentage.
    """
    roadmap_data = _load_roadmap_data()
    tracker_data = _load_tracker_data()
    current_day = tracker_data.get("current_day", 1)
    phase_info = _get_phase_for_day(roadmap_data, current_day)
    total_days = len(roadmap_data.get("daily_tasks", {}))
    progress_percentage = (
        round(((current_day - 1) / total_days * 100), 2) if total_days > 0 else 0
    )
    summary = {
        "name": roadmap_data.get("name", "Unnamed Roadmap"),
        "status": tracker_data.get("status", "not_started"),
        "current_day": current_day,
        "current_phase": phase_info.get("title") if phase_info else "N/A",
        "start_date": tracker_data.get("start_date"),
        "progress_percentage": progress_percentage,
    }
    return json.dumps(summary, indent=2)


@mcp.tool()
def get_tasks_for_day(day_number: Optional[int] = None) -> str:
    """
    Get the tasks and phase for a specific day in the roadmap.

    This tool fetches the list of tasks and the phase title for a given day number. If no day is provided, it defaults to the current day from the tracker. Returns a JSON object with the roadmap name, day's number, phase, and tasks. Use this tool to display or retrieve the user's daily learning or project tasks.

    Args:
        day_number (Optional[int]): The day number to get tasks for. If None, uses the current day.

    Returns:
        str: JSON string with keys: name, day, phase, tasks. Returns an error message if no tasks are found for the day.
    """
    roadmap_data = _load_roadmap_data()
    tracker_data = _load_tracker_data()
    target_day = (
        day_number if day_number is not None else tracker_data.get("current_day", 1)
    )
    tasks_info = roadmap_data.get("daily_tasks", {}).get(str(target_day))
    if not tasks_info:
        return f"Error: No tasks found for Day {target_day}."
    phase_info = _get_phase_for_day(roadmap_data, target_day)
    result = {
        "name": roadmap_data.get("name", "Unnamed Roadmap"),
        "day": target_day,
        "phase": phase_info.get("title") if phase_info else "N/A",
        "tasks": tasks_info.get("tasks", []),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def complete_day() -> str:
    """
    Mark the current day as complete and advance to the next day in the roadmap.

    This tool logs the completion of the current day in the tracker's history, increments the current day, and updates the status. If the last day is completed, it marks the roadmap as 'completed'. Use this tool when the user finishes all tasks for the day and is ready to move forward.

    Returns:
        str: Confirmation message with the new current day, or a congratulatory message if the roadmap is finished. Returns an error if the roadmap is not in progress.
    """
    tracker = _load_tracker_data()
    if tracker.get("status") != "in_progress":
        return (
            "Error: Roadmap is not currently in progress. Use 'start_roadmap' to begin."
        )
    current_day = tracker["current_day"]
    tracker["history"][str(current_day)] = datetime.date.today().isoformat()
    tracker["current_day"] += 1
    total_days = len(_load_roadmap_data().get("daily_tasks", {}))
    if tracker["current_day"] > total_days:
        tracker["status"] = "completed"
        _save_tracker_data(tracker)
        return f"Congratulations! You've completed Day {current_day} and finished the entire roadmap!"
    _save_tracker_data(tracker)
    return f"Great job on completing Day {current_day}! You are now on Day {tracker['current_day']}."


if __name__ == "__main__":
    print("Starting Roadmap Tracker MCP Server...")
    print("\n--- Available Tools ---")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"- {tool.name}")
    print("\nConnect your multi-tool agent to use this server.")
    mcp.run()
