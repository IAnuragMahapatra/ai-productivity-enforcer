import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

# Initialize the MCP instance
mcp = FastMCP("Productivity Enforcer")
DATA_FILE = Path(__file__).parent.parent / "data" / "productivity_data.json"


def _get_default_data() -> Dict[str, Any]:
    """Returns the default structure for the data file."""
    return {
        "plan": {},
        "reports": {},
        "long_term_tasks": {},
        "analytics": {
            "problem_tasks": {},
            "completion_trends": {"last_7_days": 0.0, "last_30_days": 0.0},
            "dedication_percentage": 0.7,
            "absence_counter": 0,
            "last_task_date": datetime.now().strftime("%Y-%m-%d"),
            "semester_phase": "N/A",
            "consecutive_high_intensity_days": 0,
            "burnout_risk": "low",
            "absence_log": [],
            "holidays_log": [],
        },
    }


def _load_data() -> Dict[str, Any]:
    """Loads productivity data, creating a default file if necessary."""
    try:
        if DATA_FILE.exists() and DATA_FILE.stat().st_size > 0:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    DATA_FILE.parent.mkdir(exist_ok=True)
    default_data = _get_default_data()
    _save_data(default_data)
    return default_data


def _save_data(data: Dict[str, Any]):
    """Saves the provided data dictionary to the JSON file."""
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _get_recent_reports(data: Dict[str, Any], days: int) -> List[Dict[str, Any]]:
    """Helper to get reports from the last N days."""
    recent_reports = []
    today = datetime.now().date()
    for date_str, report in data.get("reports", {}).items():
        try:
            report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if (
                today - report_date
            ).days < days:  # Use < to include today up to N days ago
                recent_reports.append(report)
        except (ValueError, TypeError):
            continue

    return recent_reports


def _update_absence_counter():
    """Internal function to update the absence counter based on the last interaction date."""
    data = _load_data()
    analytics = data.get("analytics", {})
    last_task_date_str = analytics.get("last_task_date")
    if not last_task_date_str:
        return  # Cannot calculate without a last task date

    last_task_date = datetime.strptime(last_task_date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    delta = (today - last_task_date).days

    # The absence counter is the number of full days *missed* between tasks
    analytics["absence_counter"] = max(0, delta - 1)
    _save_data(data)


def _calculate_dedication_percentage(data: Dict[str, Any]) -> float:
    """Calculates dedication based on completion and consistency."""
    analytics = data.get("analytics", {})
    reports_14_days = _get_recent_reports(data, 14)
    completion_rate_14_days = (
        sum(r["completion_rate"] for r in reports_14_days) / len(reports_14_days)
        if reports_14_days
        else 0.0
    )
    unexplained_absences = analytics.get("absence_counter", 0)
    consistency_score = max(0, 1.0 - (unexplained_absences * 0.2))
    # Up to 3 consecutive high intensity days is good, more than 3 is bad
    high_intensity_task_days = analytics.get("consecutive_high_intensity_days", 0)
    if high_intensity_task_days <= 3:
        intensity_factor = 1.0
    else:
        intensity_factor = max(0, 1.0 - ((high_intensity_task_days - 3) * 0.25))
    dedication = (
        (completion_rate_14_days * 0.5)
        + (consistency_score * 0.3)
        + (intensity_factor * 0.2)
    )
    return round(dedication, 2)


def _calculate_burnout_risk(data: Dict[str, Any]) -> str:
    """Calculates burnout risk based on intensity, performance, dedication, and phase."""
    analytics = data.get("analytics", {})
    risk_score = 0.0
    intensity = analytics.get("consecutive_high_intensity_days", 0)
    if intensity >= 3:
        risk_score += 0.3
    if intensity >= 5:
        risk_score += 0.2
    completion_trend = analytics.get("completion_trends", {}).get("last_7_days", 0.7)
    if completion_trend < 0.6:
        risk_score += 0.2
    dedication = analytics.get("dedication_percentage", 0.7)
    if dedication < 0.5:
        risk_score += 0.1
    phase = analytics.get("semester_phase")
    if phase in ["mid_semester", "late_semester"]:
        risk_score += 0.15
    if phase == "finals_period":
        risk_score += 0.25
    if analytics.get("absence_counter", 0) > 2:
        risk_score += 0.1

    if risk_score >= 0.8:
        return "critical"
    if risk_score >= 0.6:
        return "high"
    if risk_score >= 0.4:
        return "medium"
    return "low"


def _update_full_analytics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrates the recalculation of all key analytics metrics."""
    _update_absence_counter()
    reports_7_days = _get_recent_reports(data, 7)
    reports_30_days = _get_recent_reports(data, 30)
    avg_7 = (
        sum(r["completion_rate"] for r in reports_7_days) / len(reports_7_days)
        if reports_7_days
        else 0.0
    )
    avg_30 = (
        sum(r["completion_rate"] for r in reports_30_days) / len(reports_30_days)
        if reports_30_days
        else 0.0
    )
    data["analytics"]["completion_trends"] = {
        "last_7_days": round(avg_7, 2),
        "last_30_days": round(avg_30, 2),
    }
    data["analytics"]["dedication_percentage"] = _calculate_dedication_percentage(data)
    data["analytics"]["burnout_risk"] = _calculate_burnout_risk(data)
    return data


def _recommend_rest_or_light_day(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Proactively checks if a rest or light day is needed before planning.
    Returns a dict with recommendation and reason.
    """
    analytics = data["analytics"]
    burnout_risk = analytics["burnout_risk"]
    intensity = analytics.get("consecutive_high_intensity_days", 0)
    holidays_log = analytics.get("holidays_log", [])
    if holidays_log:
        last_holiday_date = datetime.strptime(
            holidays_log[-1]["date"], "%Y-%m-%d"
        ).date()
        if (datetime.now().date() - last_holiday_date).days <= 2:
            return {
                "recommendation": "PROCEED_NORMALLY",
                "reason": "A day off was taken very recently.",
            }
    if burnout_risk == "critical":
        return {
            "recommendation": "MANDATORY_REST",
            "reason": "Critical burnout risk detected. Rest is required.",
        }
    if burnout_risk == "high":
        return {
            "recommendation": "RECOMMENDED_REST",
            "reason": "High burnout risk detected.",
        }
    if burnout_risk == "medium" or intensity >= 3:
        return {
            "recommendation": "RECOMMENDED_LIGHT_DAY",
            "reason": "Burnout risk is medium or user has had 3+ high-intensity days.",
        }
    return {
        "recommendation": "PROCEED_NORMALLY",
        "reason": "Analytics indicate user is ready for a productive day.",
    }


@mcp.tool()
def check_readiness_for_planning() -> str:
    """
    Checks if planning can proceed today, or if there is an unreported plan blocking progress.

    **Instructions:**
    - Always call this tool before planning a new day.
    - Use the returned status to decide next steps.

    **Warnings:**
    - If status is BLOCKED, do NOT proceed with planning until the missing report is logged.
    - If status is PLAN_EXIST, do NOT overwrite today's plan.
    - If status is ALREADY_REPORTED, today's task is already completed and reported; do not plan again.

    Returns:
      - If all clear: readiness status, rest/light day recommendation, long-term tasks, analytics, and instructions.
      - If blocked: details of the unreported plan.
      - If plan exists: details of today's plan.
      - If already reported: today's report and a brief comment on performance.
    """
    data = _load_data()
    today_str = str(datetime.now().date())
    unreported_dates = sorted(
        [
            date
            for date in data["plan"]
            if date not in data["reports"] and date < today_str
        ]
    )
    if unreported_dates:
        earliest = unreported_dates[0]
        return json.dumps(
            {
                "status": "BLOCKED",
                "message": f"Unreported plan for {earliest}. Accountability check required.",
                "details": {
                    "unreported_date": earliest,
                    "tasks": data["plan"].get(earliest, {}).get("tasks", []),
                },
            },
            indent=2,
        )

    if today_str in data.get("plan", {}):
        analytics = data.get("analytics", {})
        return json.dumps(
            {
                "status": "PLAN_EXIST",
                "message": f"There is already a plan for today, {today_str}.",
                "plan": data["plan"],
                "semester_phase": analytics.get("semester_phase"),
            },
            indent=2,
        )

    if today_str in data.get("reports", {}):
        report = data["reports"][today_str]
        completion = report.get("completion_rate", 0)
        if completion >= 0.9:
            comment = "Excellent work! See you tomorrow."
        elif completion >= 0.75:
            comment = "Good job, see you tomorrow."
        elif completion >= 0.5:
            comment = "Decent effort, see you tomorrow."
        else:
            comment = "Try to improve tomorrow."
        return json.dumps(
            {
                "status": "ALREADY_REPORTED",
                "report": report,
                "comment": comment,
            },
            indent=2,
        )

    data = _update_full_analytics(data)
    rest_or_light_day = _recommend_rest_or_light_day(data)
    long_term_tasks = data.get("long_term_tasks", {})
    instruction = "First if absence_counter > 0, address it according to Absence Management Protocol. Then check the status of long-term tasks using the respective MCP tools (If no dedicated MCP exists, use the 'Memory Store', Also use the same to check specific tasks for a particular day of the week.)."
    analytics = data.get("analytics", {})
    day_of_week = datetime.now().strftime("%A")
    return json.dumps(
        {
            "status": "READY",
            "rest_or_light_day": rest_or_light_day,
            "long_term_tasks": long_term_tasks,
            "instruction": instruction,
            "day_of_week": day_of_week,
            "semester_phase": analytics.get("semester_phase"),
            "absence_counter": analytics.get("absence_counter"),
        },
        indent=2,
    )


@mcp.tool()
def get_recent_reports(days: int = 4) -> str:
    """
    Returns daily reports from the last N days (default: 4).

    **Instructions:**
    - Use this to review recent performance or for analytics.

    **Warnings:**
    - Only call when you need recent report data; avoid unnecessary calls to save tokens.

    Args:
        days (int): Number of days to look back (including today).
    Returns:
        str: JSON list of report objects.
    """
    data = _load_data()
    reports = _get_recent_reports(data, days)
    return json.dumps(reports, indent=2)


@mcp.tool()
def report(
    date: str,
    completed: List[str],
    partial: List[Dict],
    skipped: List[Dict],
    was_absent: bool,
    absence_reason: str = "",
    was_holiday: bool = False,
    holiday_reason: str = "",
) -> str:
    """
    Logs the completion status for a daily plan, or logs a legitimate absence or holiday.

    **Instructions:**
    - Use for logging daily results, absences, or holidays.
    - For holidays/rest days, set was_holiday=True.
    - For absences, set was_absent=True.
    - For consecutive holidays or absences, log only one entry with the date field as a range (e.g., "2025-07-15 to 2025-07-23").

    **Warnings:**
    - Do NOT log a report for a date without a plan (except for absences/holidays).
    - Logging a holiday resets intensity counters and does not create a report.
    - Logging an absence does not create a report.

    Returns:
        str: JSON confirmation and any triggered pattern alerts.
    """
    data = _load_data()
    today_str = datetime.now().strftime("%Y-%m-%d")

    if was_holiday:
        data["analytics"]["holidays_log"].append(
            {"date": date, "reason": holiday_reason, "logged_at": today_str}
        )
        data["analytics"]["consecutive_high_intensity_days"] = 0
        _save_data(data)
        return json.dumps(
            {"status": f"Holiday for {date} logged successfully."}, indent=2
        )

    if was_absent:
        data["analytics"]["absence_log"].append(
            {"date": date, "reason": absence_reason, "logged_at": today_str}
        )
        data["analytics"]["consecutive_high_intensity_days"] = 0
        _save_data(data)
        return json.dumps({"status": "Absence logged successfully."}, indent=2)

    original_plan = data.get("plan", {}).get(date)
    if not original_plan:
        return json.dumps({"error": f"No plan found for date {date}."})

    total_tasks = len(original_plan.get("tasks", []))
    completion_rate = len(completed) / total_tasks if total_tasks > 0 else 0.0

    # Normal report logic (not absence/holiday)
    data["reports"][date] = {
        "completed": completed,
        "partial": partial,
        "skipped": skipped,
        "completion_rate": round(completion_rate, 2),
        "reported_at": datetime.now().isoformat(),
    }

    # Update problem task analytics and trigger patterns
    analytics = data["analytics"]
    triggered_patterns = []
    for task in skipped:
        task_name_base = task["name"].split(" ")[0]
        if task_name_base not in analytics["problem_tasks"]:
            analytics["problem_tasks"][task_name_base] = {
                "skip_count": 0,
                "skip_reasons": [],
            }
        analytics["problem_tasks"][task_name_base]["skip_count"] += 1
        analytics["problem_tasks"][task_name_base]["skip_reasons"].append(
            task.get("reason", "unknown")
        )
        if analytics["problem_tasks"][task_name_base]["skip_count"] >= 3:
            triggered_patterns.append(f"3rd_skip_pattern for {task_name_base}")

    # CORRECT INTEGRATION: After logging new performance data, recalculate all analytics.
    data = _update_full_analytics(data)
    _save_data(data)
    return json.dumps(
        {
            "status": "Report logged successfully.",
            "new_dedication": data["analytics"]["dedication_percentage"],
            "triggered_patterns": triggered_patterns,
        },
        indent=2,
    )


@mcp.tool()
def set_daily_plan(
    date: str, tasks: List[Dict], context: str, energy_level: str
) -> str:
    """
    Creates and stores the user's plan for a specific day, replacing the existing plan.

    **Instructions:**
    - Only use after check_readiness_for_planning returns READY.
    - For holidays or rest days, use the report tool instead.

    **Warnings:**
    - This will overwrite all existing plans.
    - Do NOT use for holidays/rest days.

    Returns:
        str: JSON of the stored plan.
    """
    data = _load_data()
    plan_data = {
        "tasks": tasks,
        "context": context,
        "energy_level": energy_level,
        "total_time": sum(task.get("estimated_time", 0) for task in tasks),
        "created_at": datetime.now().isoformat(),
    }

    data["plan"] = {date: plan_data}

    analytics = data["analytics"]
    analytics["last_task_date"] = date
    analytics["absence_counter"] = 0
    if context == "hectic" or plan_data["total_time"] > 5:
        analytics["consecutive_high_intensity_days"] = (
            analytics.get("consecutive_high_intensity_days", 0) + 1
        )
    else:
        analytics["consecutive_high_intensity_days"] = 0
    _save_data(data)
    return json.dumps(plan_data, indent=2)


@mcp.tool()
def get_analytics_context() -> str:
    """
    Retrieves a comprehensive, up-to-date snapshot of the user's productivity analytics.

    **Instructions:**
    - Use to fetch the latest analytics after any report or plan change.

    **Warnings:**
    - Only call when analytics context is explicitly needed to save tokens.

    Returns:
        str: JSON analytics object.
    """
    data = _load_data()
    # CORRECT INTEGRATION: Always provide the freshest data when explicitly asked for analytics.
    data = _update_full_analytics(data)
    _save_data(data)
    return json.dumps(data.get("analytics", {}), indent=2)


@mcp.tool()
def update_semester_phase(phase: str) -> str:
    """
    Updates the current semester phase, which adjusts system expectations and analytics.

    **Instructions:**
    - Use when the academic phase changes (e.g., start/end of semester, finals).

    **Warnings:**
    - Only valid phases: early_semester, mid_semester, late_semester, finals_period, semester_break.
    - Invalid phase will return an error.

    Args:
        phase (str): The new semester phase.
    Returns:
        str: JSON status and new phase.
    """
    data = _load_data()
    valid_phases = [
        "early_semester",
        "mid_semester",
        "late_semester",
        "finals_period",
        "semester_break",
    ]
    if phase not in valid_phases:
        return json.dumps({"error": f"Invalid phase. Must be one of {valid_phases}."})
    data["analytics"]["semester_phase"] = phase
    _save_data(data)
    return json.dumps({"status": "success", "new_phase": phase})


@mcp.tool()
def show_long_term_tasks() -> str:
    """
    Shows all long-term tasks/goals and their current status and metadata.

    **Instructions:**
    - Call only before editing, or when the user explicitly requests to view long-term tasks.

    **Warnings:**
    - Avoid unnecessary calls to save tokens.

    Returns:
        str: JSON of long-term tasks.
    """
    data = _load_data()
    return json.dumps(data.get("long_term_tasks", {}), indent=2)


@mcp.tool()
def edit_long_term_tasks(new_tasks: dict) -> str:
    """
    Replaces the entire long_term_tasks section with the provided dictionary.

    **Instructions:**
    - Use to add, update, or delete long-term tasks.
    - Omit tasks from new_tasks to delete them.

    **Warnings:**
    - This will overwrite all existing long-term tasks.

    Args:
      new_tasks: The new dictionary of long-term tasks.
    Returns:
      str: JSON of updated long-term tasks.
    """
    data = _load_data()
    data["long_term_tasks"] = new_tasks
    _save_data(data)
    return json.dumps(data["long_term_tasks"], indent=2)


@mcp.tool()
def validate_day_off_request() -> str:
    """
    Analyzes a user's explicit request for a day off (rest/holiday).

    **Instructions:**
    - Use to check if a day off is permissible based on analytics and recent breaks.

    **Warnings:**
    - Only call when the user requests a day off.

    Returns:
      str: JSON with permissibility score and reasoning.
    """
    data = _load_data()
    # CORRECT INTEGRATION: Ensure analytics are fresh before calculating the score.
    data = _update_full_analytics(data)
    analytics = data["analytics"]
    score = 0.5
    reasons = []

    dedication = analytics.get("dedication_percentage", 0.7)
    score += (dedication - 0.7) * 0.5
    reasons.append(f"Dedication is at {int(dedication * 100)}%.")

    phase = analytics.get("semester_phase")
    if phase in ["mid_semester", "late_semester", "finals_period"]:
        score += 0.2
        reasons.append(
            "Current semester phase is critical, allow for a day off if it will be spent for academic work."
        )
    elif phase == "early_semester":
        score -= 0.2
        reasons.append("Current semester phase is early, a day off is not recommended.")
    elif phase == "semester_break":
        score += 0.2
        reasons.append("It is currently a semester break.")

    holidays_log = analytics.get("holidays_log", [])
    if holidays_log:
        last_holiday_date = datetime.strptime(
            holidays_log[-1]["date"], "%Y-%m-%d"
        ).date()
        if (datetime.now().date() - last_holiday_date).days <= 4:
            score -= 0.4
            reasons.append("A day off was taken in the last 4 days.")

    if analytics["burnout_risk"] in ["high", "critical"]:
        score += 0.3
        reasons.append("Burnout risk is high.")

    final_score = max(0.0, min(1.0, score))
    return json.dumps(
        {"permissibility_score": round(final_score, 2), "reasons": " ".join(reasons)}
    )


if __name__ == "__main__":
    _load_data()
    print("Starting Productivity-Assistant MCP Server...")
    print("\n--- Available Tools ---")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"- {tool.name}")
    print("\nConnect your multi-tool agent to use this server.")
    mcp.run()
