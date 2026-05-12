# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run test (Web UI — manual control)
```bash
locust -f locustfile.py
# Open http://localhost:8089, set users & spawn rate, then Start
# When StairStepShape is active, the user/spawn-rate fields are disabled — comment it out to enable manual input
```

### Run test (headless — automated 3-minute stair-step)
```bash
locust -f locustfile.py --headless --run-time 3m \
       --html moodle_report.html --csv moodle_results
```

## Architecture

### locustfile.py

Two top-level classes — both must remain at module level (not nested):

**`MoodleManagerUser(HttpUser)`** — the virtual user that performs a 5-step login-then-create-course flow per iteration:
1. `on_start` → `_login()`: GET `/login/index.php` to scrape `logintoken`, then POST credentials. Scrapes `sesskey` from the post-login dashboard HTML.
2. `@task create_course`: GET the course edit form, then POST it with all required Moodle fields.
3. `on_stop` → logout via `GET /logout?sesskey=…`

**`StairStepShape(LoadTestShape)`** — controls the automated ramp-up (5 → 20 → 50 users over 3 minutes). When this class exists in the file, Locust disables manual user/spawn-rate input in the Web UI. Comment it out to re-enable manual control.

**`validate_slos` (`@events.quitting`)** — runs after the test ends, prints a pass/fail verdict, and sets exit code 1 if any SLO is breached.

### Critical Moodle-specific details

- **`logintoken`**: CSRF token scraped from the login page HTML before every login. Without it, the POST is rejected.
- **`sesskey`**: Session key scraped from the dashboard HTML after login. Must be included in every POST and in the logout URL.
- **`_qf__course_edit_form: "1"`**: Moodle form identifier field — omitting it causes the form POST to be silently ignored (no course created, but 200 returned).
- `_scrape_hidden()` handles two HTML attribute orderings (`name=… value=…` and `value=… name=…`).

### SLOs (defined as constants at the top of locustfile.py)

| Constant | Value | Meaning |
|---|---|---|
| `P95_SLO_MS` | 3000 | P95 response time must be < 3 s |
| `FAILURE_RATE_SLO` | 5 | Error rate must be < 5% |
| `MIN_RPS_SLO` | 5 | Throughput must be ≥ 5 req/s |

SLO breaches are detected per-request using `catch_response=True` + `resp.failure(...)`. Any response slower than `P95_SLO_MS` ms is counted as a failure.

### Output files

| File | Content |
|---|---|
| `moodle_report.html` | Full HTML report with charts |
| `moodle_results_stats.csv` | Per-endpoint stats + aggregated row |
| `moodle_results_stats_history.csv` | Time-series RPS/response-time data |
| `moodle_results_failures.csv` | Failure messages and counts |
| `performance_test_report.md` | Human-readable analysis and conclusions |
