import asyncio
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Projects Status Tracker")
PROJECTS_FILE = Path(__file__).parent.parent / "data" / "projects_status.json"


def _load_data() -> Dict[str, Any]:
    try:
        if os.path.exists(PROJECTS_FILE) and os.path.getsize(PROJECTS_FILE) > 0:
            with PROJECTS_FILE.open("r") as f:
                return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    default_data = {"status": []}
    _save_data(default_data)
    return default_data


def _save_data(data: Dict[str, Any]):
    with PROJECTS_FILE.open("w") as f:
        json.dump(data, f, indent=4)


def _find_project(
    data: Dict[str, Any], project_id: Optional[int] = None, title: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if project_id is None and title is None:
        return None

    for status_group in data.get("status", []):
        for task in status_group.get("tasks", []):
            # Prioritize ID for accuracy
            if project_id is not None and task.get("id") == project_id:
                return task
            # Fallback to title if ID is not provided or not found
            if title is not None and task.get("title") == title:
                return task
    return None


def _get_next_id(data: Dict[str, Any]) -> int:
    max_id = 0
    for status_group in data.get("status", []):
        for task in status_group.get("tasks", []):
            if "id" in task and task["id"] > max_id:
                max_id = task["id"]
    return max_id + 1


def _get_current_focus(data: Dict[str, Any]) -> List[int]:
    """
    Returns the list of project IDs currently in focus. If not set, returns an empty list.
    """
    return data.get("current_focus", [])


def _set_current_focus(data: Dict[str, Any], focus_ids: List[int]):
    """
    Sets the list of project IDs currently in focus.
    """
    data["current_focus"] = focus_ids
    _save_data(data)


@mcp.tool()
def get_current_focus() -> str:
    """
    Returns the list of project IDs currently in focus.

    Returns:
        str: A JSON formatted list of project IDs, or an empty list if none are set.
    """
    data = _load_data()
    return json.dumps(_get_current_focus(data), indent=2)


@mcp.tool()
def set_current_focus(focus_ids: List[int]) -> str:
    """
    Sets the list of project IDs currently in focus. Overwrites any previous value.

    Args:
        focus_ids (List[int]): List of project IDs to set as current focus.

    Returns:
        str: Confirmation message or error if any ID is invalid.
    """
    data = _load_data()
    # Validate that all IDs exist
    all_ids = set()
    for status_group in data.get("status", []):
        for task in status_group.get("tasks", []):
            all_ids.add(task.get("id"))
    invalid_ids = [pid for pid in focus_ids if pid not in all_ids]
    if invalid_ids:
        return f"Error: The following project IDs do not exist: {invalid_ids}"
    _set_current_focus(data, focus_ids)
    return f"Successfully set current focus to project IDs: {focus_ids}"


@mcp.tool()
def get_all_status_categories() -> str:
    """
    Returns a list of all available status categories in the project tracker.
    This is a low-cost query to understand the overall structure of the projects.

    Returns:
        str: A JSON formatted string containing a list of category titles (e.g., ["On Queue", "Completed", ...]).
    """
    data = _load_data()
    categories = [status_group.get("title") for status_group in data.get("status", [])]
    return json.dumps(categories, indent=2)


@mcp.tool()
def get_projects_by_status(status_category: str) -> str:
    """
    Retrieves all projects within a specific status category.

    Args:
        status_category (str): The exact title of the status category to query (e.g., 'Need Work', 'Completed').

    Returns:
        str: A JSON formatted string of the projects in that category, or an error message if not found.
    """
    data = _load_data()
    for status_group in data.get("status", []):
        if status_group.get("title") == status_category:
            return json.dumps(status_group.get("tasks", []), indent=2)
    return f"Error: Status category '{status_category}' not found."


@mcp.tool()
def get_project(project_id: Optional[int] = None, title: Optional[str] = None) -> str:
    """
    Finds and returns a single project by its unique ID or title.
    Using project_id is preferred as it is guaranteed to be unique.

    Args:
        project_id (Optional[int]): The unique ID of the project.
        title (Optional[str]): The exact title of the project.

    Returns:
        str: A JSON formatted string of the project if found, otherwise an error message.
    """
    if project_id is None and title is None:
        return "Error: You must provide either a 'project_id' or a 'title'."

    data = _load_data()
    project = _find_project(data, project_id=project_id, title=title)

    if project:
        return json.dumps(project, indent=2)
    else:
        return "Error: Project not found with specified ID or title."


@mcp.tool()
def search_projects(keyword: str) -> str:
    """
    Searches for projects by a keyword. Performs a case-insensitive, partial match against project titles and tags.

    Args:
        keyword (str): The keyword to search for (e.g., "os", "agentic", "game").

    Returns:
        str: A JSON formatted string of found projects, or a message if no matches are found.
    """
    data = _load_data()
    found_projects = []
    lower_keyword = keyword.lower()

    # Use a set to store IDs of projects already found to avoid duplicates
    found_ids = set()

    for status_group in data.get("status", []):
        for task in status_group.get("tasks", []):
            task_id = task.get("id")
            if task_id in found_ids:
                continue

            # Check title for a partial, case-insensitive match
            title_match = lower_keyword in task.get("title", "").lower()

            # Check tags for a partial, case-insensitive match
            tag_match = any(
                lower_keyword in tag.lower() for tag in task.get("tags", [])
            )

            if title_match or tag_match:
                # Add a 'current_status' field for better context in search results
                result_task = task.copy()
                result_task["current_status"] = status_group.get("title")
                found_projects.append(result_task)
                found_ids.add(task_id)

    if not found_projects:
        return f"No projects found matching the keyword: '{keyword}'."

    return json.dumps(found_projects, indent=2)


@mcp.tool()
def get_all_projects() -> str:
    """
    Reads and returns all data from the projects_status.json file.
    WARNING: This can be a very large output and consume many tokens.
    Prefer using `get_all_status_categories`, `get_projects_by_status`, or `get_project` for more targeted queries.

    Returns:
        str: A JSON formatted string containing all project data.
    """
    data = _load_data()
    return json.dumps(data, indent=2)


@mcp.tool()
def update_project_completion(
    new_completion: int, project_id: Optional[int] = None, title: Optional[str] = None
) -> str:
    """
    Updates the completion percentage for a specific project, found by ID (preferred) or title.

    Args:
        new_completion (int): The new completion percentage (0-100).
        project_id (Optional[int]): The unique ID of the project to update.
        title (Optional[str]): The exact title of the project to update (used if ID is not provided).

    Returns:
        str: A confirmation message or an error if the project was not found or input is invalid.
    """
    if project_id is None and title is None:
        return "Error: You must provide either a 'project_id' or a 'title'."

    if not (0 <= new_completion <= 100):
        return "Error: Completion percentage must be between 0 and 100."

    data = _load_data()
    project_to_update = _find_project(data, project_id=project_id, title=title)

    if project_to_update:
        project_title = project_to_update.get("title", "N/A")
        project_to_update["completion"] = new_completion
        _save_data(data)
        return f"Successfully updated '{project_title}' (ID: {project_to_update.get('id')}) to {new_completion}% completion."
    else:
        return "Error: Project not found."


@mcp.tool()
def update_project_status(project_id: int, new_status_category: str) -> str:
    """
    Moves a project to a different status category using its unique ID.

    Args:
        project_id (int): The unique ID of the project to move.
        new_status_category (str): The exact title of the destination category (e.g., 'Finishing Touches').

    Returns:
        str: A confirmation message indicating success or an error if the project or category was not found.
    """
    data = _load_data()
    project_to_move = None
    original_list_ref = None
    project_title = ""

    # Find the project and store a reference to its original list to remove it later
    for status_group in data.get("status", []):
        tasks = status_group.get("tasks", [])
        for i, task in enumerate(tasks):
            if task.get("id") == project_id:
                # Found the project, pop it from its current list
                project_to_move = tasks.pop(i)
                project_title = project_to_move.get("title", "N/A")
                original_list_ref = tasks  # This is for potential rollback
                break
        if project_to_move:
            break

    if not project_to_move:
        return f"Error: Project with ID {project_id} not found."

    # Find the destination category and add the project
    destination_found = False
    for status_group in data.get("status", []):
        if status_group.get("title") == new_status_category:
            status_group.get("tasks", []).append(project_to_move)
            destination_found = True
            break

    if not destination_found:
        # If the destination wasn't found, roll back the change by re-inserting the project.
        if original_list_ref is not None:
            original_list_ref.append(project_to_move)
        return f"Error: Destination status category '{new_status_category}' not found. The project was not moved."

    _save_data(data)
    return f"Successfully moved project '{project_title}' (ID: {project_id}) to '{new_status_category}'."


@mcp.tool()
def add_project(
    status_category: str,
    title: str,
    estimated_time: int,
    completion: int = 0,
    effort: str = "medium",
    reward: str = "medium",
    tags: Optional[List[str]] = None,
) -> str:
    """
    Adds a new project to a specified status category. A unique ID will be automatically assigned.

    Args:
        status_category (str): The category to add the project to (e.g., 'On Queue').
        title (str): The title of the new project.
        estimated_time (int): The total estimated time in hours to complete the project from start to finish.
        completion (int, optional): The initial completion percentage. Defaults to 0.
        effort (str, optional): The estimated effort ('low', 'medium', 'high', etc.). Defaults to 'medium'.
        reward (str, optional): The estimated reward. Defaults to 'medium'.
        tags (Optional[List[str]], optional): A list of tags for the project. Defaults to an empty list.

    Returns:
        str: Confirmation message of success or failure.
    """
    data = _load_data()
    category_found = False

    new_task = {
        "id": _get_next_id(data),
        "title": title,
        "completion": completion,
        "effort": effort,
        "reward": reward,
        "tags": tags if tags is not None else [],
        "estimated_time": estimated_time,
    }

    for status_group in data.get("status", []):
        if status_group.get("title") == status_category:
            if "tasks" not in status_group:
                status_group["tasks"] = []
            status_group["tasks"].append(new_task)
            category_found = True
            break

    if category_found:
        _save_data(data)
        return f"Successfully added project '{title}' (ID: {new_task['id']}) to '{status_category}'."
    else:
        return f"Error: Status category '{status_category}' not found. Use get_all_status_categories to see valid options."


@mcp.tool()
def delete_project(
    project_id: Optional[int] = None, title: Optional[str] = None
) -> str:
    """
    Deletes a project from the tracker by its unique ID or title.
    Using project_id is preferred as it is guaranteed to be unique.

    Args:
        project_id (Optional[int]): The unique ID of the project to delete.
        title (Optional[str]): The exact title of the project to delete (used if ID is not provided).

    Returns:
        str: A confirmation message if the project was deleted, or an error if not found.
    """
    if project_id is None and title is None:
        return "Error: You must provide either a 'project_id' or a 'title' to delete a project."

    data = _load_data()
    project_found = False
    deleted_project_info = ""

    # Iterate through a copy of the status groups to safely modify the original
    for status_group in data.get("status", []):
        tasks = status_group.get("tasks", [])

        # We need to find the index to pop it safely while iterating
        index_to_delete = -1
        for i, task in enumerate(tasks):
            # Prioritize ID for an exact match
            if project_id is not None and task.get("id") == project_id:
                index_to_delete = i
                break
            # Fallback to title if no ID was given
            elif (
                project_id is None and title is not None and task.get("title") == title
            ):
                index_to_delete = i
                break

        if index_to_delete != -1:
            # Remove the task by its index
            deleted_task = tasks.pop(index_to_delete)
            project_found = True
            deleted_project_info = f"'{deleted_task.get('title', 'N/A')}' (ID: {deleted_task.get('id', 'N/A')})"
            break  # Exit the main loop once the project is found and deleted

    if project_found:
        _save_data(data)
        return f"Successfully deleted project {deleted_project_info}."
    else:
        # Construct a specific error message
        if project_id:
            return f"Error: Project with ID '{project_id}' not found."
        else:
            return f"Error: Project with title '{title}' not found."


@mcp.tool()
def get_project_summary() -> str:
    """
    Returns the current summary block from the project data, if it exists.
    The summary includes total project counts, estimated hours, category breakdowns, top tags, and effort/reward distributions.
    To update the summary, use `update_project_summary`.

    Returns:
        str: A JSON formatted string of the summary block, or an error if not found.
    """
    data = _load_data()
    summary_data = data.get("summary")

    if summary_data:
        return json.dumps(summary_data, indent=2)
    else:
        return "Error: Summary block not found. Please run `update_project_summary` to generate it."


@mcp.tool()
def update_project_summary() -> str:
    """
    Recalculates and updates the summary block in the project data.
    The summary includes total project counts, estimated hours, completed/in-progress/queued counts, category breakdowns, top tags, and effort/reward distributions.
    This should be run after adding, deleting, or updating projects to keep the summary up to date.

    Returns:
        str: A confirmation message after updating the summary.
    """
    data = _load_data()
    all_tasks = []

    # Initialize counters and totals
    category_counts = Counter()
    effort_counts = Counter()
    reward_counts = Counter()
    all_tags = []
    total_estimated_hours = 0

    # Define which categories count as 'in progress' vs 'queued'
    in_progress_statuses = [
        "Just Documentation / Readme",
        "Finishing Touches",
        "Need Work",
        "Just Started",
    ]

    for status_group in data.get("status", []):
        category_title = status_group.get("title", "Unknown")
        tasks = status_group.get("tasks", [])

        category_counts[category_title] = len(tasks)

        for task in tasks:
            all_tasks.append(task)
            total_estimated_hours += task.get("estimated_time", 0)
            effort_counts[task.get("effort", "unknown")] += 1
            reward_counts[task.get("reward", "unknown")] += 1
            all_tags.extend(task.get("tags", []))

    # Calculate high-level project counts
    completed_projects = category_counts.get("Completed", 0)
    queued_projects = category_counts.get("On Queue", 0)
    in_progress_projects = sum(
        category_counts.get(status, 0) for status in in_progress_statuses
    )

    # Get the top 7 most common tags
    top_tags = [tag for tag, count in Counter(all_tags).most_common(7)]

    # Assemble the new summary object
    new_summary = {
        "total_projects": len(all_tasks),
        "total_estimated_hours": total_estimated_hours,
        "completed_projects": completed_projects,
        "in_progress_projects": in_progress_projects,
        "queued_projects": queued_projects,
        "categories": dict(category_counts),
        "top_tags": top_tags,
        "effort_distribution": dict(effort_counts),
        "reward_distribution": dict(reward_counts),
    }

    # Replace the old summary in the data and save
    data["summary"] = new_summary
    _save_data(data)

    return "Successfully recalculated and updated the project summary."


if __name__ == "__main__":
    print("Starting Projects Status MCP Server...")
    print("\n--- Available Tools ---")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"- {tool.name}")
    print("\nConnect your multi-tool agent to use this server.")
    mcp.run()
