# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A helpdesk app (tickets and ticket statistics) over an **existing, live** MongoDB Atlas collection:
`neerus.tickets` (308 documents). FastAPI + PyMongo backend in `backend/`, React + Vite (plain JavaScript)
dashboard in `frontend/`. Reference data lives in `neerus.departments` (8 documents) and `neerus.stores` (7).

Status: **project scaffold only.** No application code exists yet. It follows the same approach as the sibling
sales project (`C:\Users\vijen\inventory-management`, repo `manishpolishetty51-pixel/sales-data`), which can be
used as a reference for structure, error handling, tests and UI patterns.

"Ticket stats" is **not** a separate collection. There is none in the database. Statistics must be calculated
from the real ticket records with aggregation queries.

## Build order (follow strictly)

1. Inspect this directory, then connect to Atlas read-only and re-verify the schema below before coding.
2. Report the findings and field mappings; do not guess.
3. Backend, then tests against real data (reads) and fakes (writes), then frontend, then end-to-end checks.
4. README with setup steps.

## Known data model (verify before relying on it)

`neerus.tickets`: integer `_id` equal to `id` (no ObjectId), `text` (the ticket message), `staff` (who raised it),
`staffRole` (Store Manager, Sales Associate, Stock Handler, Cashier, Corporate), `store` (7 stores plus `Corporate`),
`dept` (department it was routed to), `status`, `createdAt` (epoch **milliseconds**, float), `replies`
(list of `{from, text, at}`; 0 to 2 per ticket today), and AI-routing metrics `latency` (int) and `cost` (float).
Fields `error` and `stock` are null on every current document; `product` is null on about two thirds and an
object on the rest (inspect its keys before using it). `latency` and `cost` are null on 8 tickets, so never treat
them as always present. The units of `latency` and `cost` are not documented: confirm before labelling them.

Values seen today: `status` is `routed` on all 308 tickets (do not assume other statuses exist, and do not invent
an open/closed workflow without approval). `dept` values: Procurement, Maintenance, IT, HR, Logistics, Finance,
Loss Prevention, Marketing, Corporate. Note `Corporate` appears on tickets but **not** in `neerus.departments`
(which has Finance, HR, IT, Logistics, Loss Prevention, Maintenance, Marketing, Procurement), so never assume
every ticket `dept` joins to a department document.

`neerus.departments`: string `_id` equal to `id`, `name`, `handles`, `leader`.
`neerus.stores`: string `_id` equal to `id`, `name`, `hasLogin`, `staff` (list).

## Planned features

- Tickets list with pagination (`skip`/`limit`, max 100), newest first; search over text, staff and store;
  filters for department, store, status, staff role and date range; sort by date.
- Ticket detail with the full reply thread.
- Statistics: total tickets, tickets per department, per store, per staff role, per day or week, average and
  maximum latency, total and average cost, reply counts and tickets with no reply. Compute only from present
  values; skip nulls rather than treating them as zero.
- Write support (create ticket, add reply, update) only after the user confirms the intended workflow, because
  the data has a single status value today. Deleting tickets needs an explicit confirmation dialog.

## Privacy rules

Tickets contain staff names and free text that may include personal details. Never log ticket text, staff names
or reply content, and never include them in error messages. Mention individual tickets only by id in logs and tests.
Do not paste real ticket text into docs, commits, tests or chat summaries; use fabricated placeholders in tests.

## Commands (once built)

Backend, from `backend/` using the project venv (`.venv\Scripts\python.exe` on Windows):

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000   # API + /docs
.\.venv\Scripts\python.exe -m pytest                                  # all tests
```

Frontend, from `frontend/`: `npm run dev` (http://localhost:5173, proxies `/api` to port 8000) and `npm run build`.

## Configuration

`backend/.env` is git-ignored and must never be printed, read aloud or committed. Provide `backend/.env.example`
with placeholders only. Variables: `MONGODB_URI`, `DATABASE_NAME=neerus`, `COLLECTION_NAME=tickets`,
`DEPARTMENTS_COLLECTION=departments`, `CORS_ORIGINS`, `API_KEY`. The same Atlas URI as the sales project is
used; the user copies it in themselves.

## Rules carried over from the sales project

- Write endpoints (POST/PUT/DELETE) require an `X-API-Key` header matching `API_KEY`. The key is typed into the UI and
  kept in localStorage; never bundle or hardcode it.
- Updates are partial (`$set` of only the sent fields); never replace whole documents or add fields to existing ones.
- New ids are `max(id) + 1`. Timestamps are epoch milliseconds; date filters take epoch ms, inclusive, and the
  frontend converts local-day boundaries.
- Never write to the live database from tests. Use an in-memory fake for CRUD; live tests are read-only and skip
  without a URI. Manual write checks: create, edit, delete one clearly named temporary record, then confirm counts.
- Never print or log `MONGODB_URI`, credentials or `API_KEY`. Map database errors to 503/504/403 without leaking details.
- In FastAPI routes, create a **new** `Query(...)` object per parameter. Sharing one instance makes several filters read
  the same query key and silently return unfiltered results.
- Use the Write tool for source files; large Windows Bash heredoc chains can break. Never name a scratch script `inspect.py`.

## Git

- Never push directly to `main`; use a feature branch and a pull request.
- Pushes can stall on a Git Credential Manager sign-in window. Run them in the background and check the output.
- Remote for this project has not been chosen yet. Ask before creating or pushing to one.
