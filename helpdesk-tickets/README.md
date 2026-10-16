# Helpdesk: tickets and ticket stats

FastAPI + PyMongo backend and a React (Vite, plain JavaScript) dashboard over the live MongoDB Atlas
collection `neerus.tickets`. Statistics are calculated from the ticket records with aggregation queries;
there is no separate stats collection. This version is **read-only**.

## Setup

1. Backend, from `backend/`:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   copy .env.example .env      # then fill in MONGODB_URI and API_KEY
   .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
   ```

   API docs: http://localhost:8000/docs. If port 8000 is taken (for example by the sales project), run on
   another port and change the proxy target in `frontend/vite.config.js` to match.

2. Frontend, from `frontend/`:

   ```powershell
   npm install
   npm run dev     # http://localhost:5173, proxies /api to port 8000
   npm run build
   ```

3. Tests, from `backend/`: `.\.venv\Scripts\python.exe -m pytest`. Live tests only read, and skip when
   `MONGODB_URI` is not set.

`backend/.env` is git-ignored. Never commit or share it.

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Database connectivity and ticket count |
| `GET /api/tickets` | Paginated list (`skip`, `limit` max 100, `sort=asc\|desc`), newest first |
| `GET /api/tickets/{id}` | One ticket with its full reply thread |
| `GET /api/stats` | Totals, per department/store/role/status, per `period=day\|week`, latency, cost, replies |
| `GET /api/filters` | Distinct values for the filter drop-downs |
| `GET /api/departments` | Reference departments |

Filters on list and stats: `q` (text, staff, store), `dept`, `store`, `status`, `staff_role`,
`date_from`, `date_to` (epoch milliseconds, inclusive).

## Notes

- `latency` and `cost` units are not documented; the UI labels them without units. Nulls are skipped in
  averages, not counted as zero.
- `Corporate` is a ticket department with no document in `neerus.departments`.
- Create, reply, update and delete are not built yet: the data has a single status (`routed`), so the
  intended workflow needs confirming first. When added, writes will require the `X-API-Key` header.
