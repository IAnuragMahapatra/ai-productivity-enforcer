import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Profile Manager")
USER_DATA_FILE = Path(__file__).parent.parent / "data" / "user_data.json"


def _load_data() -> Dict[str, Any]:
    with USER_DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_data(data: Dict[str, Any]):
    with USER_DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


@mcp.tool()
def get_persona_snapshot() -> str:
    """
    Returns a holistic snapshot of the user's professional persona, including their elevator pitch, contact info, education, work style, and career goals.
    This is the ideal starting point for most agent tasks that need a summary of the user's identity and preferences.

    Returns:
        str: A JSON string summarizing the user's core professional identity, including persona_summary, basic_info, education, work_style, and ideal_roles.
    """
    data = _load_data()
    snapshot = {
        "persona_summary": data.get("persona_summary"),
        "basic_info": data.get("basic_info"),
        "education": data.get("education"),
        "work_style": data.get("work_style"),
        "ideal_roles": data.get("ideal_roles"),
    }
    return json.dumps(snapshot, indent=2)


@mcp.tool()
def get_data_by_section(section_name: str) -> str:
    """
    Retrieves all data from a specific top-level section of the profile.
    Valid sections are: 'persona_summary', 'basic_info', 'education', 'skills', 'leadership', 'work_style', 'ideal_roles', 'experience', 'certification'.
    If 'projects' is requested, returns a message instructing the agent to use the Projects Status MCP instead.

    Args:
        section_name (str): The name of the section to retrieve.

    Returns:
        str: A JSON string of the section's data, or an error message if not found.
    """
    data = _load_data()
    if section_name in data:
        if section_name == "projects":
            return json.dumps(
                {
                    "message": "Project data is managed by the 'Projects Status MCP'. Use that tool to query projects."
                }
            )
        return json.dumps(data[section_name], indent=2)
    return f"Error: Section '{section_name}' not found."


@mcp.tool()
def update_field(section_name: str, field: str, new_value: Any) -> str:
    """
    Updates a single field within a specified top-level section of the user's profile.
    Only allows updates to existing fields in existing sections. Returns a confirmation or error message.

    Args:
        section_name (str): The name of the section to update (must exist in the profile).
        field (str): The name of the field to update (must exist in the section).
        new_value (Any): The new value for the field.

    Returns:
        str: A confirmation message if successful, or an error message if the section or field is not found.
    """
    data = _load_data()
    if section_name in data and isinstance(data[section_name], dict):
        if field in data[section_name]:
            data[section_name][field] = new_value
            _save_data(data)
            return f"Successfully updated '{section_name}.{field}'."
        return f"Error: Field '{field}' not found in section '{section_name}'."
    return f"Error: Section '{section_name}' not found or is not a dictionary section."


@mcp.tool()
def add_field(section_name: str, field: str, value: Any) -> str:
    """
    Adds a new field to a specified dictionary section in the user's profile.
    Returns an error if the section does not exist, is not a dictionary, or the field already exists.

    Args:
        section_name (str): The name of the section to add the field to.
        field (str): The name of the new field to add.
        value (Any): The value to set for the new field.

    Returns:
        str: A confirmation message if successful, or an error message if the section/field is invalid.
    """
    data = _load_data()
    if section_name in data and isinstance(data[section_name], dict):
        if field in data[section_name]:
            return f"Error: Field '{field}' already exists in section '{section_name}'."
        data[section_name][field] = value
        _save_data(data)
        return f"Successfully added field '{field}' to section '{section_name}'."
    return f"Error: Section '{section_name}' not found or is not a dictionary section."


@mcp.tool()
def delete_field(section_name: str, field: str) -> str:
    """
    Deletes a field from a specified dictionary section in the user's profile.
    Returns an error if the section or field does not exist, or if the section is not a dictionary.

    Args:
        section_name (str): The name of the section to delete the field from.
        field (str): The name of the field to delete.

    Returns:
        str: A confirmation message if successful, or an error message if the section/field is invalid.
    """
    data = _load_data()
    if section_name in data and isinstance(data[section_name], dict):
        if field in data[section_name]:
            del data[section_name][field]
            _save_data(data)
            return (
                f"Successfully deleted field '{field}' from section '{section_name}'."
            )
        return f"Error: Field '{field}' not found in section '{section_name}'."
    return f"Error: Section '{section_name}' not found or is not a dictionary section."


@mcp.tool()
def update_section(section_name: str, new_data: Any) -> str:
    """
    Updates the entire content of a specified top-level section in the user's profile.
    Overwrites the section with the provided new_data (should match the expected structure for that section).
    Returns a confirmation or error message.

    Args:
        section_name (str): The name of the section to update (must exist in the profile).
        new_data (Any): The new data to set for the section (should be a valid Python object for that section).

    Returns:
        str: A confirmation message if successful, or an error message if the section is not found.
    """
    data = _load_data()
    if section_name in data:
        data[section_name] = new_data
        _save_data(data)
        return f"Successfully updated section '{section_name}'."
    return f"Error: Section '{section_name}' not found."


@mcp.tool()
def add_section(section_name: str, section_data: Any) -> str:
    """
    Adds a new top-level section to the user's profile.
    If the section already exists, returns an error message. Otherwise, adds the section with the provided data.

    Args:
        section_name (str): The name of the new section to add.
        section_data (Any): The data to set for the new section (should be a valid Python object for that section).

    Returns:
        str: A confirmation message if successful, or an error message if the section already exists.
    """
    data = _load_data()
    if section_name in data:
        return f"Error: Section '{section_name}' already exists."
    data[section_name] = section_data
    _save_data(data)
    return f"Successfully added new section '{section_name}'."


@mcp.tool()
def delete_section(section_name: str) -> str:
    """
    Deletes an entire top-level section from the user's profile.
    Returns an error if the section does not exist.

    Args:
        section_name (str): The name of the section to delete.

    Returns:
        str: A confirmation message if successful, or an error message if the section does not exist.
    """
    data = _load_data()
    if section_name in data:
        del data[section_name]
        _save_data(data)
        return f"Successfully deleted section '{section_name}'."
    return f"Error: Section '{section_name}' not found."


if __name__ == "__main__":
    print("Starting Profile Manager MCP Server...")
    print("\n--- Available Tools ---")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"- {tool.name}")
    print("\nConnect your multi-tool agent to use this server.")
    mcp.run()
