from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

from flask import Flask, jsonify, render_template, request


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_FILE = os.path.join(APP_ROOT, "schedule.json")

# Days we support, in order
WEEKDAYS: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


# ---------- Storage model ----------
# {
#   "default": { "Monday": "", ... },
#   "overrides": { "MM/DD": { "Monday": "2–4 PM", ... } }
# }

def _default_schedule_model() -> Dict[str, Dict[str, str]]:
	"""Create a default schedule model structure.
	
	Returns:
		Dict[str, Dict[str, str]]: A dictionary with 'default' and 'overrides' keys.
		The 'default' key contains empty strings for each weekday.
		The 'overrides' key contains an empty dictionary for date-specific overrides.
		
	Example:
		{
			"default": {"Monday": "", "Tuesday": "", ...},
			"overrides": {}
		}
	"""
	return {"default": {day: "" for day in WEEKDAYS}, "overrides": {}}


def _coerce_to_model(data: object) -> Dict[str, Dict[str, str]]:
	"""Convert legacy data formats to the current schedule model structure.
	
	This function handles backward compatibility by converting old data formats
	to the current model structure. It supports both the new format with
	'default' and 'overrides' keys and the legacy flat dictionary format.
	
	Args:
		data: Raw data that could be in various formats (dict, None, etc.)
		
	Returns:
		Dict[str, Dict[str, str]]: A properly structured schedule model with
		'default' and 'overrides' keys. Invalid data is filtered out.
		
	Raises:
		No exceptions are raised; invalid data is simply ignored.
		
	Example:
		# New format (unchanged)
		{"default": {"Monday": "9-5"}, "overrides": {"12/25": {"Monday": "CLOSED"}}}
		
		# Legacy format (converted)
		{"Monday": "9-5", "Tuesday": "10-6"} -> {"default": {"Monday": "9-5", "Tuesday": "10-6"}, "overrides": {}}
	"""
	# Back-compat: if old flat dict, wrap as default
	model = _default_schedule_model()
	if isinstance(data, dict):
		if "default" in data and "overrides" in data and isinstance(data["default"], dict) and isinstance(data["overrides"], dict):
			# Clean keys
			for day, val in data["default"].items():
				if day in model["default"] and isinstance(val, str):
					model["default"][day] = val
			for dstr, mapping in data["overrides"].items():
				if isinstance(mapping, dict):
					model["overrides"][dstr] = {}
					for day, val in mapping.items():
						if day in model["default"] and isinstance(val, str):
							model["overrides"][dstr][day] = val
			return model
		# Old format: {"Monday": ""}
		for day, val in data.items():
			if day in model["default"] and isinstance(val, str):
				model["default"][day] = val
	return model


def load_schedule_model() -> Dict[str, Dict[str, str]]:
	"""Load schedule model from disk, or return default if not present/invalid.
	
	This function attempts to load the schedule data from the JSON file.
	If the file doesn't exist, is corrupted, or contains invalid data,
	a default empty schedule model is returned instead.
	
	Returns:
		Dict[str, Dict[str, str]]: The loaded schedule model with 'default' and 'overrides' keys.
		If loading fails, returns a default model with empty values.
		
	Side Effects:
		None. This is a read-only operation.
		
	Example:
		model = load_schedule_model()
		# Returns: {"default": {"Monday": "9-5", ...}, "overrides": {"12/25": {...}}}
	"""
	if not os.path.exists(SCHEDULE_FILE):
		return _default_schedule_model()
	try:
		with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
			data = json.load(f)
			return _coerce_to_model(data)
	except Exception:
		return _default_schedule_model()


def save_schedule_model(model: Dict[str, Dict[str, str]]) -> None:
	"""Save the schedule model to disk as a JSON file.
	
	This function persists the current schedule model to the schedule.json file.
	The file is saved with pretty-printing (2-space indentation) and UTF-8 encoding.
	
	Args:
		model: The schedule model dictionary to save. Must contain 'default' and 'overrides' keys.
		
	Raises:
		OSError: If the file cannot be written to disk.
		TypeError: If the model cannot be serialized to JSON.
		
	Side Effects:
		Creates or overwrites the schedule.json file.
		
	Example:
		model = {"default": {"Monday": "9-5"}, "overrides": {}}
		save_schedule_model(model)
	"""
	with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
		json.dump(model, f, indent=2, ensure_ascii=False)


# In-memory cache; load on startup
_model: Dict[str, Dict[str, str]] = load_schedule_model()


# ---------- Public helper functions ----------

def set_default_time(day: str, start_time: str = "", end_time: str = "") -> Dict[str, Dict[str, str]]:
	"""Set default time for a weekday using 24-hour format.
	
	This function sets the default office hours for a specific weekday.
	Times are provided in 24-hour format and converted to a readable format.
	Empty times result in "CLOSED" status. The change is immediately saved to disk.
	
	Args:
		day: Weekday name (case-insensitive, e.g., "monday", "Monday", "MONDAY")
		start_time: Start time in 'XX:XX' 24-hour format (e.g., '14:00') or empty string for CLOSED
		end_time: End time in 'XX:XX' 24-hour format (e.g., '17:00') or empty string for CLOSED
		
	Returns:
		Dict[str, Dict[str, str]]: The updated schedule model after the change
		
	Raises:
		ValueError: If the day is not a valid weekday (Monday-Friday)
		OSError: If the schedule file cannot be written to disk
		
	Side Effects:
		Updates the in-memory model and saves changes to schedule.json
		
	Example:
		# Set Monday to 2:00 PM - 5:00 PM
		model = set_default_time("Monday", "14:00", "17:00")
		
		# Close Tuesday
		model = set_default_time("Tuesday", "", "")
	"""
	day_norm = day.strip().capitalize()
	if day_norm not in WEEKDAYS:
		raise ValueError(f"Invalid day: {day}. Expected one of {', '.join(WEEKDAYS)}")
	formatted_time = _format_time_range(start_time, end_time)
	_model["default"][day_norm] = formatted_time
	save_schedule_model(_model)
	return _model


def set_default_bulk(new_times: Dict[str, str]) -> Dict[str, Dict[str, str]]:
	"""Set default times for multiple weekdays in a single operation.
	
	This function allows setting default office hours for multiple weekdays
	at once. Each time value should be in a format that can be parsed by
	the time formatting system (typically "HH:MM-HH:MM" or "CLOSED").
	
	Args:
		new_times: Dictionary mapping weekday names to time strings
			Keys should be weekday names (case-insensitive)
			Values should be time strings (e.g., "14:00-17:00" or "CLOSED")
		
	Returns:
		Dict[str, Dict[str, str]]: The updated schedule model after all changes
		
	Raises:
		TypeError: If new_times is not a dictionary
		ValueError: If any weekday name is invalid
		OSError: If the schedule file cannot be written to disk
		
	Side Effects:
		Updates the in-memory model and saves changes to schedule.json
		
	Example:
		times = {
			"Monday": "14:00-17:00",
			"Tuesday": "10:00-12:00",
			"Wednesday": "CLOSED"
		}
		model = set_default_bulk(times)
	"""
	if not isinstance(new_times, dict):
		raise TypeError("new_times must be a dict of {day: time}")
	for day, time_value in new_times.items():
		set_default_time(day, str(time_value))
	return _model


def _format_time_range(start_time: str, end_time: str) -> str:
	"""Convert 24-hour times to readable 12-hour format.
	
	This internal function converts 24-hour time strings to a human-readable
	12-hour format with AM/PM indicators. Empty or invalid times result in "CLOSED".
	
	Args:
		start_time: Start time in 'XX:XX' 24-hour format (e.g., '14:00')
		end_time: End time in 'XX:XX' 24-hour format (e.g., '17:00')
		
	Returns:
		str: Formatted time range in 12-hour format (e.g., '2:00 PM - 5:00 PM')
			or 'CLOSED' if either time is empty or invalid
		
	Raises:
		No exceptions are raised; invalid input results in "CLOSED"
		
	Example:
		_format_time_range("14:00", "17:00")  # Returns "2:00 PM - 5:00 PM"
		_format_time_range("09:30", "12:00")  # Returns "9:30 AM - 12:00 PM"
		_format_time_range("", "17:00")       # Returns "CLOSED"
		_format_time_range("invalid", "17:00") # Returns "CLOSED"
	"""
	if not start_time or not end_time or start_time.strip() == "" or end_time.strip() == "":
		return "CLOSED"
	
	try:
		# Parse 24-hour format
		start_hour, start_min = map(int, start_time.split(':'))
		end_hour, end_min = map(int, end_time.split(':'))
		
		# Convert to 12-hour format
		def to_12hour(hour, minute):
			if hour == 0:
				return f"12:{minute:02d} AM"
			elif hour < 12:
				return f"{hour}:{minute:02d} AM"
			elif hour == 12:
				return f"12:{minute:02d} PM"
			else:
				return f"{hour-12}:{minute:02d} PM"
		
		start_12 = to_12hour(start_hour, start_min)
		end_12 = to_12hour(end_hour, end_min)
		
		return f"{start_12} - {end_12}"
	except (ValueError, IndexError):
		return "CLOSED"


def temp_change(date_mmdd: str, start_time: str = "", end_time: str = "") -> Dict[str, Dict[str, str]]:
	"""Set a temporary override for a specific date.
	
	This function creates a date-specific override that takes precedence over
	the default schedule. The override applies to all weekdays on the specified date.
	Empty times result in "CLOSED" status for that date.
	
	Args:
		date_mmdd: Date in 'MM/DD' format (e.g., '09/16' for September 16th)
		start_time: Start time in 'XX:XX' 24-hour format (e.g., '14:00') or empty for CLOSED
		end_time: End time in 'XX:XX' 24-hour format (e.g., '17:00') or empty for CLOSED
		
	Returns:
		Dict[str, Dict[str, str]]: The updated schedule model after the change
		
	Raises:
		ValueError: If the date format is invalid (not MM/DD)
		OSError: If the schedule file cannot be written to disk
		
	Side Effects:
		Updates the in-memory model and saves changes to schedule.json
		
	Example:
		# Set September 16th to 2:00 PM - 5:00 PM
		model = temp_change("09/16", "14:00", "17:00")
		
		# Close September 16th
		model = temp_change("09/16", "", "")
	"""
	_d = _normalize_mmdd(date_mmdd)
	formatted_time = _format_time_range(start_time, end_time)
	_model["overrides"][_d] = formatted_time
	save_schedule_model(_model)
	return _model


def temp_change_for_date(date_mmdd: str, updates: Dict[str, str]) -> Dict[str, Dict[str, str]]:
	"""Set multiple day overrides for a single date (same 'MM/DD').
	
	This function allows setting different office hours for different weekdays
	on the same date. This is useful for special events or holidays that affect
	only certain days of the week on a specific date.
	
	Args:
		date_mmdd: Date in 'MM/DD' format (e.g., '09/16' for September 16th)
		updates: Dictionary mapping weekday names to time strings
			Keys should be weekday names (case-insensitive)
			Values should be time strings (e.g., "14:00-17:00" or "CLOSED")
		
	Returns:
		Dict[str, Dict[str, str]]: The updated schedule model after the change
		
	Raises:
		TypeError: If updates is not a dictionary
		ValueError: If the date format is invalid (not MM/DD)
		OSError: If the schedule file cannot be written to disk
		
	Side Effects:
		Updates the in-memory model and saves changes to schedule.json
		
	Example:
		# Set different hours for different days on September 16th
		updates = {
			"Monday": "14:00-17:00",
			"Tuesday": "CLOSED",
			"Wednesday": "10:00-12:00"
		}
		model = temp_change_for_date("09/16", updates)
	"""
	_d = _normalize_mmdd(date_mmdd)
	if not isinstance(updates, dict):
		raise TypeError("updates must be a dict of {day: time}")
	bucket = _model["overrides"].setdefault(_d, {})
	for day, time_value in updates.items():
		day_norm = str(day).strip().capitalize()
		if day_norm in WEEKDAYS:
			bucket[day_norm] = str(time_value)
	save_schedule_model(_model)
	return _model


def temp_change_week(week_monday_mmdd: str, week_times: Dict[str, str]) -> Dict[str, Dict[str, str]]:
	"""Apply a weekly batch: for the week starting Monday (MM/DD), set overrides for Mon–Fri.
	
	This function sets office hours for an entire week starting from a Monday.
	It creates date-specific overrides for each day of the week (Monday through Friday)
	based on the provided Monday date. This is useful for setting special schedules
	for holidays, breaks, or other week-long events.
	
	Args:
		week_monday_mmdd: Monday date in 'MM/DD' format (e.g., '09/23' for September 23rd)
		week_times: Dictionary mapping weekday names to time strings
			Keys should be weekday names (case-insensitive)
			Values should be time strings (e.g., "14:00-17:00" or "CLOSED")
		
	Returns:
		Dict[str, Dict[str, str]]: The updated schedule model after the change
		
	Raises:
		ValueError: If week_monday_mmdd is not a Monday or date format is invalid
		OSError: If the schedule file cannot be written to disk
		
	Side Effects:
		Updates the in-memory model and saves changes to schedule.json
		
	Example:
		# Set special hours for the week of September 23rd
		week_times = {
			"Monday": "10:00-12:00",
			"Tuesday": "CLOSED",
			"Wednesday": "14:00-17:00",
			"Thursday": "10:00-12:00",
			"Friday": "CLOSED"
		}
		model = temp_change_week("09/23", week_times)
	"""
	monday_date = _parse_mmdd_in_current_year(week_monday_mmdd)
	# Ensure provided date is a Monday
	if monday_date.weekday() != 0:
		raise ValueError("week_monday_mmdd must be a Monday")
	for i, day_name in enumerate(WEEKDAYS):
		d = monday_date + timedelta(days=i)
		dstr = d.strftime("%m/%d")
		if day_name in week_times:
			_model["overrides"].setdefault(dstr, {})[day_name] = str(week_times[day_name])
	save_schedule_model(_model)
	return _model


# ---------- Effective schedule computation ----------

def _normalize_mmdd(mmdd: str) -> str:
	"""Normalize a date string to MM/DD format.
	
	This internal function validates and normalizes date strings to ensure
	they are in the correct MM/DD format. It parses the input and reformats
	it to ensure consistency.
	
	Args:
		mmdd: Date string in MM/DD format (e.g., '9/16', '09/16', '9/6')
		
	Returns:
		str: Normalized date string in MM/DD format (e.g., '09/16')
		
	Raises:
		ValueError: If the date format is invalid or cannot be parsed
		
	Example:
		_normalize_mmdd("9/16")   # Returns "09/16"
		_normalize_mmdd("09/16")  # Returns "09/16"
		_normalize_mmdd("invalid") # Raises ValueError
	"""
	try:
		return _parse_mmdd_in_current_year(mmdd).strftime("%m/%d")
	except Exception:
		raise ValueError("date must be in MM/DD format")


def _parse_mmdd_in_current_year(mmdd: str) -> date:
	"""Parse a MM/DD date string and return a date object for the current year.
	
	This internal function converts a MM/DD format string to a Python date object
	by appending the current year. This is used for date calculations and validations.
	
	Args:
		mmdd: Date string in MM/DD format (e.g., '09/16')
		
	Returns:
		date: Python date object for the specified date in the current year
		
	Raises:
		ValueError: If the date format is invalid or the date doesn't exist
		
	Example:
		_parse_mmdd_in_current_year("09/16")  # Returns date(2024, 9, 16)
		_parse_mmdd_in_current_year("02/29")  # May raise ValueError in non-leap years
	"""
	return datetime.strptime(f"{mmdd}/{date.today().year}", "%m/%d/%Y").date()


def start_of_week_monday(any_date: date) -> date:
	"""Calculate the Monday date for the week containing the given date.
	
	This function finds the Monday of the week that contains the specified date.
	It's used to determine week boundaries for schedule calculations.
	
	Args:
		any_date: Any date to find the Monday of its week
		
	Returns:
		date: The Monday date of the week containing any_date
		
	Example:
		start_of_week_monday(date(2024, 9, 18))  # Returns date(2024, 9, 16) (Wednesday -> Monday)
		start_of_week_monday(date(2024, 9, 16))  # Returns date(2024, 9, 16) (Monday -> Monday)
		start_of_week_monday(date(2024, 9, 22))  # Returns date(2024, 9, 16) (Sunday -> Monday)
	"""
	return any_date - timedelta(days=any_date.weekday())


def effective_week_schedule(week_monday: date) -> List[Tuple[str, str, str]]:
	"""Return list of tuples: (weekday_name, MM/DD, effective_time).
	
	This function calculates the effective schedule for a week starting from
	the given Monday. It considers both default weekday schedules and any
	date-specific overrides to determine the actual office hours for each day.
	
	Args:
		week_monday: The Monday date of the week to calculate the schedule for
		
	Returns:
		List[Tuple[str, str, str]]: List of tuples containing:
			- weekday_name: Name of the weekday (e.g., "Monday")
			- MM/DD: Date string in MM/DD format (e.g., "09/16")
			- effective_time: The effective office hours for that day
			  (from override if exists, otherwise from default)
		
	Example:
		week_monday = date(2024, 9, 16)
		schedule = effective_week_schedule(week_monday)
		# Returns: [("Monday", "09/16", "2:00 PM - 5:00 PM"), ...]
	"""
	result: List[Tuple[str, str, str]] = []
	for i, day_name in enumerate(WEEKDAYS):
		d = week_monday + timedelta(days=i)
		dstr = d.strftime("%m/%d")
		override = _model["overrides"].get(dstr)
		effective = override if (override is not None and override != "") else _model["default"].get(day_name, "")
		result.append((day_name, dstr, effective or ""))
	return result


app = Flask(__name__)


@app.get("/")
def index():
	"""Display the current week's office hours schedule.
	
	This Flask route renders the main page showing the effective office hours
	for the current week. It calculates the schedule by finding the Monday
	of the current week and determining the effective hours for each weekday,
	considering both default schedules and any date-specific overrides.
	
	Returns:
		str: Rendered HTML template with the current week's schedule
		
	Template Variables:
		rows: List of tuples containing (weekday_name, MM/DD, effective_time)
		
	Example:
		GET / -> Renders index.html with current week's schedule
	"""
	# Compute current week's effective schedule
	week_monday = start_of_week_monday(date.today())
	rows = effective_week_schedule(week_monday)
	return render_template("index.html", rows=rows)


@app.get("/next-week")
def next_week():
	"""Display next week's office hours schedule.
	
	This Flask route renders a page showing the effective office hours
	for next week. It calculates the schedule by finding the Monday of
	the following week and determining the effective hours for each weekday,
	considering both default schedules and any date-specific overrides.
	
	Returns:
		str: Rendered HTML template with next week's schedule
		
	Template Variables:
		rows: List of tuples containing (weekday_name, MM/DD, effective_time)
		
	Example:
		GET /next-week -> Renders index.html with next week's schedule
	"""
	# Simulate next week's schedule
	week_monday = start_of_week_monday(date.today()) + timedelta(days=7)
	rows = effective_week_schedule(week_monday)
	return render_template("index.html", rows=rows)


@app.get("/api/schedule")
def api_get_schedule():
	"""Get the complete schedule model as JSON.
	
	This API endpoint returns the entire schedule model including both
	default weekday schedules and all date-specific overrides. This is
	useful for external applications that need access to the raw schedule data.
	
	Returns:
		Response: JSON response containing the complete schedule model
		
	JSON Structure:
		{
			"default": {"Monday": "9:00 AM - 5:00 PM", ...},
			"overrides": {"09/16": "CLOSED", "12/25": {"Monday": "CLOSED", ...}}
		}
		
	Example:
		GET /api/schedule -> Returns JSON with complete schedule data
	"""
	return jsonify(_model)


@app.post("/api/schedule/default")
def api_set_default():
	"""Set default office hours via API.
	
	This API endpoint allows setting default office hours for weekdays.
	It supports both single day updates and bulk updates for multiple days.
	
	Request Body (JSON):
		Single day: {"day": "Monday", "time": "14:00-17:00"}
		Bulk update: {"Monday": "14:00-17:00", "Tuesday": "CLOSED", ...}
		
	Returns:
		Response: JSON response containing the updated schedule model
		
	Status Codes:
		200: Success - Returns updated schedule model
		400: Bad Request - Invalid JSON body or missing required fields
		
	Example:
		POST /api/schedule/default
		{"day": "Monday", "time": "14:00-17:00"}
		-> Returns updated model with Monday set to 2:00 PM - 5:00 PM
	"""
	payload = request.get_json(silent=True) or {}
	if "day" in payload and "time" in payload and isinstance(payload["day"], str):
		updated = set_default_time(payload["day"], str(payload.get("time", "")))
		return jsonify(updated)
	if not isinstance(payload, dict):
		return jsonify({"error": "Invalid JSON body"}), 400
	updated = set_default_bulk({k: str(v) for k, v in payload.items()})
	return jsonify(updated)


@app.post("/api/schedule/override")
def api_set_override():
	"""Set temporary overrides for specific dates via API.
	
	This API endpoint allows setting date-specific overrides that take
	precedence over default schedules. It supports both single day overrides
	and multi-day overrides for the same date.
	
	Request Body (JSON):
		Single day: {"date": "09/16", "day": "Monday", "time": "14:00-17:00"}
		Multi-day: {"date": "09/16", "updates": {"Monday": "14:00-17:00", "Tuesday": "CLOSED"}}
		
	Returns:
		Response: JSON response containing the updated schedule model
		
	Status Codes:
		200: Success - Returns updated schedule model
		400: Bad Request - Invalid JSON body or missing required fields
		
	Example:
		POST /api/schedule/override
		{"date": "09/16", "day": "Monday", "time": "14:00-17:00"}
		-> Returns updated model with September 16th Monday override
	"""
	payload = request.get_json(silent=True) or {}
	# Single day override
	if all(k in payload for k in ("date", "day", "time")):
		updated = temp_change(str(payload["date"]), str(payload["day"]), str(payload.get("time", "")))
		return jsonify(updated)
	# Multi-day for a single date
	if "date" in payload and "updates" in payload and isinstance(payload["updates"], dict):
		updated = temp_change_for_date(str(payload["date"]), {k: str(v) for k, v in payload["updates"].items()})
		return jsonify(updated)
	return jsonify({"error": "Expected {date, day, time} or {date, updates}"}), 400


@app.post("/api/schedule/override/week")
def api_set_override_week():
	"""Set overrides for an entire week via API.
	
	This API endpoint allows setting office hours for an entire week starting
	from a Monday. It creates date-specific overrides for each day of the week
	(Monday through Friday) based on the provided Monday date.
	
	Request Body (JSON):
		{
			"monday": "09/23",
			"times": {
				"Monday": "14:00-17:00",
				"Tuesday": "CLOSED",
				"Wednesday": "10:00-12:00",
				"Thursday": "14:00-17:00",
				"Friday": "CLOSED"
			}
		}
		
	Returns:
		Response: JSON response containing the updated schedule model
		
	Status Codes:
		200: Success - Returns updated schedule model
		400: Bad Request - Invalid JSON body or missing required fields
		
	Example:
		POST /api/schedule/override/week
		{"monday": "09/23", "times": {"Monday": "14:00-17:00", "Tuesday": "CLOSED"}}
		-> Returns updated model with week of September 23rd overrides
	"""
	payload = request.get_json(silent=True) or {}
	if not ("monday" in payload and "times" in payload and isinstance(payload["times"], dict)):
		return jsonify({"error": "Expected {monday: 'MM/DD', times: {Monday..Friday}}"}), 400
	updated = temp_change_week(str(payload["monday"]), {k: str(v) for k, v in payload["times"].items()})
	return jsonify(updated)


if __name__ == "__main__":
	# Test the temp_change function for today (09/16) with 24-hour format
	temp_change("09/16", "14:00", "17:00")  # 2:00 PM - 5:00 PM
	print("Test: Set 09/16 to 14:00-17:00 (2:00 PM - 5:00 PM)")
	
	# Set override for next week (09/23 - Monday next week)
	temp_change("09/23", "10:00", "12:00")  # 10:00 AM - 12:00 PM
	print("Test: Set 09/23 (next Monday) to 10:00-12:00 (10:00 AM - 12:00 PM)")
	
	# Run development server
	app.run(host="0.0.0.0", port=5000, debug=True)
	
