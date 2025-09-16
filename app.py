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

def set_default_time(day: str, time_value: str) -> Dict[str, Dict[str, str]]:
	day_norm = day.strip().capitalize()
	if day_norm not in WEEKDAYS:
		raise ValueError(f"Invalid day: {day}. Expected one of {', '.join(WEEKDAYS)}")
	if not isinstance(time_value, str):
		raise TypeError("time_value must be a string")
	_model["default"][day_norm] = time_value
	save_schedule_model(_model)
	return _model


def set_default_bulk(new_times: Dict[str, str]) -> Dict[str, Dict[str, str]]:
	if not isinstance(new_times, dict):
		raise TypeError("new_times must be a dict of {day: time}")
	for day, time_value in new_times.items():
		set_default_time(day, str(time_value))
	return _model


def temp_change(date_mmdd: str, day: str, time_value: str) -> Dict[str, Dict[str, str]]:
	"""Set a temporary override for a specific date and weekday.

	date_mmdd: 'MM/DD' (e.g., '09/16')
	day: Weekday name (Monday..Friday)
	"""
	day_norm = day.strip().capitalize()
	if day_norm not in WEEKDAYS:
		raise ValueError(f"Invalid day: {day}. Expected one of {', '.join(WEEKDAYS)}")
	_d = _normalize_mmdd(date_mmdd)
	_model["overrides"].setdefault(_d, {})[day_norm] = str(time_value)
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
		override = _model["overrides"].get(dstr, {}).get(day_name)
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
	# Run development server
	app.run(host="0.0.0.0", port=5000, debug=True)
