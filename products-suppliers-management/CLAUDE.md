# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A products and suppliers management app over **existing, live** MongoDB Atlas collections in the `neerus`
database: `inventory` (the product catalogue, 222 documents) and `suppliers` (10 documents). FastAPI + PyMongo
backend in `backend/`, React + Vite (plain JavaScript) dashboard in `frontend/`.

Status: **project scaffold only.** No application code exists yet. It follows the same approach as the sibling
sales project (`C:\Users\vijen\inventory-management`, repo `manishpolishetty51-pixel/sales-data`), which can be
used as a reference for structure, error handling, tests and UI patterns.

## Build order (follow strictly)

1. Inspect this directory, then connect to Atlas read-only and re-verify the schemas below before coding.
2. Report the findings and field mappings; do not guess.
3. Backend, then tests against real data (reads) and fakes (writes), then frontend, then end-to-end checks.
4. README with setup steps.

## Known data model (verify before relying on it)

`neerus.inventory` (products): integer `_id` equal to `id` (no ObjectId), unique `sku`, `name`, `type`,
`department` (Women/Men/Kids), `category`, `subCategory`, `style`, `fabric`, `occasion`, `colour`, `sizes`
(string or null; `size` is always null and ignored), `price`, `cost`, `suppliers` (list of supplier ids) and
`stock` (dict of units per store; 7 stores). There is no stored total quantity or stock status: derive both
(total units is the sum of `stock` values; low-stock threshold comes from config, default 10).

`neerus.suppliers`: integer `_id` equal to `id`, `name`, `phone`, `types` (list). Products link to suppliers
through `inventory.suppliers`.

Relationship rules to design for:
- A supplier shows the products that reference it; a product shows resolved supplier names.
- Deleting a supplier that products still reference must be blocked or require explicit confirmation. Never
  leave silent dangling ids. Deleting a product leaves old sales and transfers pointing at its id (warn in the UI).
- `phone` is PII: never log it or put it in error messages; show it only in the supplier screens.

## Commands (once built)

Backend, from `backend/` using the project venv (`.venv\Scripts\python.exe` on Windows):

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000   # API + /docs
.\.venv\Scripts\python.exe -m pytest                                  # all tests
```

Frontend, from `frontend/`: `npm run dev` (http://localhost:5173, proxies `/api` to port 8000) and `npm run build`.

## Configuration

`backend/.env` is git-ignored and must never be printed, read aloud or committed. Provide `backend/.env.example`
with placeholders only. Variables: `MONGODB_URI`, `DATABASE_NAME=neerus`, `PRODUCTS_COLLECTION=inventory`,
`SUPPLIERS_COLLECTION=suppliers`, `LOW_STOCK_THRESHOLD=10`, `CORS_ORIGINS`, `API_KEY`. The same Atlas URI as the
sales project is used; the user copies it in themselves.

## Rules carried over from the sales project

- Write endpoints (POST/PUT/DELETE) require an `X-API-Key` header matching `API_KEY`. The key is typed into the UI and
  kept in localStorage; never bundle or hardcode it.
- Updates are partial (`$set` of only the sent fields); never replace whole documents or add fields to existing ones.
  Stock updates merge per store (`stock.<store>`).
- New ids are `max(id) + 1`. SKU uniqueness is checked in code (no unique index exists; do not create one without approval).
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
