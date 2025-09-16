# OfficeHoursSignTV

A simple Flask app and static site to display and manage an office hours schedule (Monday–Friday). Supports default times and date-specific overrides.

## Setup

1. Create a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the app (dynamic)

```bash
python app.py
```

- Open `http://127.0.0.1:5000/`.
- The page shows the current week (Mon–Fri) with each day's date and effective time.
- Data persists to `schedule.json`.

## Data model (schedule.json)

```json
{
  "default": {
    "Monday": "",
    "Tuesday": "",
    "Wednesday": "",
    "Thursday": "",
    "Friday": ""
  },
  "overrides": {
    "MM/DD": {
      "Monday": "2–4 PM",
      "Wednesday": "10–12 PM"
    }
  }
}
```

- **default**: baseline weekly schedule.
- **overrides**: date-specific changes keyed by `MM/DD`. Only include days that differ from default.

## API endpoints

- **Set default times** (single or bulk):

```bash
# Single
curl -X POST http://127.0.0.1:5000/api/schedule/default \
  -H 'Content-Type: application/json' \
  -d '{"day":"Monday","time":"2–4 PM"}'

# Bulk
curl -X POST http://127.0.0.1:5000/api/schedule/default \
  -H 'Content-Type: application/json' \
  -d '{"Monday":"2–4 PM","Wednesday":"10–12 PM"}'
```

- **Temporary override for a specific date**:

```bash
# Single day override for a date
curl -X POST http://127.0.0.1:5000/api/schedule/override \
  -H 'Content-Type: application/json' \
  -d '{"date":"09/16","day":"Monday","time":"3–5 PM"}'

# Multiple days override for one date
curl -X POST http://127.0.0.1:5000/api/schedule/override \
  -H 'Content-Type: application/json' \
  -d '{"date":"09/18","updates":{"Wednesday":"CLOSED","Thursday":"1–2 PM"}}'
```

- **Weekly batch overrides** (week starting Monday):

```bash
curl -X POST http://127.0.0.1:5000/api/schedule/override/week \
  -H 'Content-Type: application/json' \
  -d '{
    "monday":"09/15",
    "times": {"Monday":"2–4 PM","Tuesday":"","Wednesday":"10–12 PM"}
  }'
```

- **Get full model**:

```bash
curl http://127.0.0.1:5000/api/schedule
```

## Using in Python code

```python
from app import set_default_time, set_default_bulk, temp_change, temp_change_for_date, temp_change_week

set_default_time("Monday", "2–4 PM")
set_default_bulk({"Wednesday": "10–12 PM", "Friday": "1–3 PM"})
temp_change("09/16", "Monday", "CLOSED")
temp_change_for_date("09/18", {"Wednesday": "", "Thursday": "2–4 PM"})
temp_change_week("09/15", {"Monday": "2–4 PM", "Wednesday": "10–12 PM"})
```

## GitHub Pages (static hosting)

- Root `index.html` reads `schedule.json` and computes the current week’s effective times in the browser.
- Styling in `static/style.css` (background is green).

To update the public schedule on GitHub Pages:
- Edit `schedule.json` and commit to the Pages branch.
- For temporary changes, add an entry under `overrides` with the `MM/DD` date.

Local preview of the static site:

```bash
python3 -m http.server 8080
# Then open http://127.0.0.1:8080/
```

Notes:
- If you use both Flask and static Pages, treat `schedule.json` as the source of truth. The Flask app writes to the same `schedule.json`, so you can update locally via the API, commit the new JSON, and push to Pages.
- GitHub Pages may cache assets; hard refresh if updates don’t appear immediately.

## Notes

- Supported days: Monday–Friday.
- Empty string means no hours set; the page shows an em dash (—).
- This app is for local or small internal use. For production, consider a real database and proper auth.