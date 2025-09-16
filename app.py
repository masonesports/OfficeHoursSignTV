from __future__ import annotations

import json
import os
from typing import Dict

from flask import Flask, jsonify, render_template, request


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_FILE = os.path.join(APP_ROOT, "schedule.json")

# Days we support, in order
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _default_schedule() -> Dict[str, str]:
	return {day: "" for day in WEEKDAYS}


def load_schedule() -> Dict[str, str]:
	"""Load schedule from disk, or return default if not present/invalid."""
	if not os.path.exists(SCHEDULE_FILE):
		return _default_schedule()
	try:
		with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
			data = json.load(f)
			# Ensure only expected keys and str values
			cleaned = _default_schedule()
			for day, time_value in (data or {}).items():
				if day in cleaned and isinstance(time_value, str):
					cleaned[day] = time_value
			return cleaned
	except Exception:
		return _default_schedule()


def save_schedule(schedule: Dict[str, str]) -> None:
	"""Persist schedule to disk."""
	with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
		json.dump(schedule, f, indent=2, ensure_ascii=False)


# In-memory cache; load on startup
_schedule: Dict[str, str] = load_schedule()


def set_time(day: str, time_value: str) -> Dict[str, str]:
	"""Set a single day's time. Returns the updated schedule.

	This function can be imported and used directly from other Python code.
	"""
	day_normalized = day.strip().capitalize()
	if day_normalized not in WEEKDAYS:
		raise ValueError(f"Invalid day: {day}. Expected one of {', '.join(WEEKDAYS)}")
	if not isinstance(time_value, str):
		raise TypeError("time_value must be a string")
	_schedule[day_normalized] = time_value
	save_schedule(_schedule)
	return _schedule


def set_schedule_bulk(new_times: Dict[str, str]) -> Dict[str, str]:
	"""Set multiple days at once. Returns the updated schedule.

	Example: {"Monday": "2-4pm", "Tuesday": ""}
	"""
	if not isinstance(new_times, dict):
		raise TypeError("new_times must be a dict of {day: time}")
	for day, time_value in new_times.items():
		set_time(day, str(time_value))
	return _schedule


app = Flask(__name__)


@app.get("/")
def index():
	# Render current schedule
	return render_template("index.html", schedule=_schedule, weekdays=WEEKDAYS)


@app.get("/api/schedule")
def api_get_schedule():
	return jsonify(_schedule)


@app.post("/api/schedule")
def api_set_schedule():
	"""Accepts JSON either as full dict or partial updates.

	Examples:
	- {"Monday": "2-4pm", "Wednesday": "1-3pm"}
	- {"day": "Monday", "time": "2-4pm"}
	"""
	payload = request.get_json(silent=True) or {}
	if "day" in payload and "time" in payload and isinstance(payload["day"], str):
		updated = set_time(payload["day"], str(payload.get("time", "")))
		return jsonify(updated)
	# Otherwise treat payload as bulk dict
	if not isinstance(payload, dict):
		return jsonify({"error": "Invalid JSON body"}), 400
	updated = set_schedule_bulk({k: str(v) for k, v in payload.items()})
	return jsonify(updated)


if __name__ == "__main__":
	# Run development server
	app.run(host="0.0.0.0", port=5000, debug=True)
