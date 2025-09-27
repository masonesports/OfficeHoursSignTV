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
	return {"default": {day: "" for day in WEEKDAYS}, "overrides": {}}


def _coerce_to_model(data: object) -> Dict[str, Dict[str, str]]:
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
	"""Load schedule model from disk, or default if not present/invalid."""
	if not os.path.exists(SCHEDULE_FILE):
		return _default_schedule_model()
	try:
		with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
			data = json.load(f)
			return _coerce_to_model(data)
	except Exception:
		return _default_schedule_model()


def save_schedule_model(model: Dict[str, Dict[str, str]]) -> None:
	with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
		json.dump(model, f, indent=2, ensure_ascii=False)


# In-memory cache; load on startup
_model: Dict[str, Dict[str, str]] = load_schedule_model()


# ---------- Public helper functions ----------

def set_default_time(day: str, start_time: str = "", end_time: str = "") -> Dict[str, Dict[str, str]]:
	"""Set default time for a weekday using 24-hour format.
	
	day: Weekday name (Monday..Friday)
	start_time: 'XX:XX' in 24-hour format (e.g., '14:00') or empty for CLOSED
	end_time: 'XX:XX' in 24-hour format (e.g., '17:00') or empty for CLOSED
	"""
	day_norm = day.strip().capitalize()
	if day_norm not in WEEKDAYS:
		raise ValueError(f"Invalid day: {day}. Expected one of {', '.join(WEEKDAYS)}")
	formatted_time = _format_time_range(start_time, end_time)
	_model["default"][day_norm] = formatted_time
	save_schedule_model(_model)
	return _model


def set_default_bulk(new_times: Dict[str, str]) -> Dict[str, Dict[str, str]]:
	if not isinstance(new_times, dict):
		raise TypeError("new_times must be a dict of {day: time}")
	for day, time_value in new_times.items():
		set_default_time(day, str(time_value))
	return _model


def _parse_flexible_time(time_str: str) -> tuple[int, int]:
	"""Parse time string in various formats and return (hour, minute) in 24-hour format.
	
	Supports formats:
	- 24-hour: "14:00", "09:30", "21:45"
	- 12-hour: "2:00PM", "9:30AM", "9:00PM", "12:00AM", "12:00PM"
	- 12-hour without colon: "2PM", "9AM", "9PM"
	"""
	time_str = time_str.strip().upper()
	
	# Handle 12-hour format with AM/PM
	if 'AM' in time_str or 'PM' in time_str:
		is_pm = 'PM' in time_str
		time_clean = time_str.replace('AM', '').replace('PM', '').strip()
		
		# Handle format like "9:00PM" or "9PM"
		if ':' in time_clean:
			hour_str, min_str = time_clean.split(':')
			hour = int(hour_str)
			minute = int(min_str)
		else:
			hour = int(time_clean)
			minute = 0
		
		# Convert to 24-hour format
		if is_pm and hour != 12:
			hour += 12
		elif not is_pm and hour == 12:
			hour = 0
		
		return hour, minute
	
	# Handle 24-hour format
	else:
		if ':' in time_str:
			hour_str, min_str = time_str.split(':')
			hour = int(hour_str)
			minute = int(min_str)
		else:
			# Handle format like "1400" -> "14:00"
			if len(time_str) == 4 and time_str.isdigit():
				hour = int(time_str[:2])
				minute = int(time_str[2:])
			else:
				raise ValueError(f"Invalid time format: {time_str}")
		
		return hour, minute


def _format_time_range(start_time: str, end_time: str) -> str:
	"""Convert flexible time formats to readable format.
	
	start_time: Time in various formats (e.g., '14:00', '2:00PM', '9:00PM')
	end_time: Time in various formats (e.g., '17:00', '5:00PM', '9:00PM')
	Returns: '2:00 PM - 5:00 PM' or 'CLOSED' if both are empty
	"""
	if not start_time or not end_time or start_time.strip() == "" or end_time.strip() == "":
		return "CLOSED"
	
	try:
		# Parse flexible time formats
		start_hour, start_min = _parse_flexible_time(start_time)
		end_hour, end_min = _parse_flexible_time(end_time)
		
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
	except (ValueError, IndexError) as e:
		return "CLOSED"


def temp_change(date_mmdd: str, start_time: str = "", end_time: str = "") -> Dict[str, Dict[str, str]]:
	"""Set a temporary override for a specific date.

	date_mmdd: 'MM/DD' (e.g., '09/16')
	start_time: 'XX:XX' in 24-hour format (e.g., '14:00') or empty for CLOSED
	end_time: 'XX:XX' in 24-hour format (e.g., '17:00') or empty for CLOSED
	"""
	_d = _normalize_mmdd(date_mmdd)
	formatted_time = _format_time_range(start_time, end_time)
	_model["overrides"][_d] = formatted_time
	save_schedule_model(_model)
	return _model


def temp_change_for_date(date_mmdd: str, updates: Dict[str, str]) -> Dict[str, Dict[str, str]]:
	"""Set multiple day overrides for a single date (same 'MM/DD')."""
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
	"""Apply a weekly batch: for the week starting Monday (MM/DD), set overrides for Mon–Fri."""
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
	try:
		return _parse_mmdd_in_current_year(mmdd).strftime("%m/%d")
	except Exception:
		raise ValueError("date must be in MM/DD format")


def _parse_mmdd_in_current_year(mmdd: str) -> date:
	return datetime.strptime(f"{mmdd}/{date.today().year}", "%m/%d/%Y").date()


def start_of_week_monday(any_date: date) -> date:
	return any_date - timedelta(days=any_date.weekday())


def effective_week_schedule(week_monday: date) -> List[Tuple[str, str, str]]:
	"""Return list of tuples: (weekday_name, MM/DD, effective_time)."""
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
	# Compute current week's effective schedule
	week_monday = start_of_week_monday(date.today())
	rows = effective_week_schedule(week_monday)
	return render_template("index.html", rows=rows)


@app.get("/next-week")
def next_week():
	# Simulate next week's schedule
	week_monday = start_of_week_monday(date.today()) + timedelta(days=7)
	rows = effective_week_schedule(week_monday)
	return render_template("index.html", rows=rows)


@app.get("/api/schedule")
def api_get_schedule():
	return jsonify(_model)


@app.post("/api/schedule/default")
def api_set_default():
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
	
