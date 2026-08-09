# Family Finance Tracker

A local-first, self-hosted app for tracking family spending and financial
health — built as its own isolated project, unrelated to the rest of this
repository. Inspired by tools like Optiml for the "financial health
score" framing, but scoped to run entirely on hardware you control.

## Why local-first

No bank credentials, no aggregator (Plaid, etc.), no cloud database.
Statements are exported by you from your bank's site as PDF, uploaded
through the app's own UI, parsed in memory, and reviewed before anything
is saved. The source PDF is never written to disk and never leaves the
machine running the backend.

## Current scope

- Upload a credit-card statement PDF → preview parsed transactions →
  edit categories inline → confirm import.
- Self-service categories (`/categories` page): add/edit keywords/delete,
  each one tagged `expense`, `income`, or `transfer`.
- **Cash flow vs. balance sheet are modeled separately, on purpose:**
  - *Cash flow* (`/dashboard`, `/transactions`): spending and income for
    a month, computed from imported transactions. Transactions in a
    `transfer`-kind category (e.g. "Credit Card Payment") are excluded
    entirely — paying off your own card is money moving between your
    own accounts, not spending or income.
  - *Balance sheet* (`/net-worth`): Assets − Liabilities = Net Worth,
    plus the change vs. last month. Since there's no bank feed, balances
    come from either a manually-recorded snapshot (works for any
    account) or, for credit cards with statements imported but no
    snapshot yet, an estimate from the running transaction total
    (clearly labeled "estimated").
- Accounts cover both sides of the balance sheet: cash, chequing,
  savings, investment, TFSA, RRSP, RESP (assets) and credit card,
  mortgage, car loan (liabilities). Credit cards optionally track a
  credit limit for an "available credit" figure.
- SQLite by default — a single file, easy to back up, easy to move to
  Postgres later by changing `DATABASE_URL`. Schema changes use small
  hand-rolled `ALTER TABLE` migrations in `backend/app/db.py` (no
  Alembic) so upgrading never requires deleting your data.
- No login. Safe today because everything stays on your own machine;
  auth is added before Phase 3 (see below).

### Statement format supported today

A tabular "Trans Date | Post Date | Description | Amount" layout with
optional "FOREIGN CURRENCY ..." sub-lines — this covers the Rogers Bank
Mastercard layout it was built against and is likely shared by other
issuers using similar statement templates. Different banks/layouts need
a new parser module under `backend/app/parsers/` — the existing one
(`creditcard_statement.py`) is a template for that; nothing else in the
app needs to change to add a second bank format.

## Running locally

### Quick start (recommended)

```bash
./start.sh
```

One command, one terminal tab. First run sets up the backend venv and
runs `npm install` automatically; later runs skip straight to starting
both services. `Ctrl+C` stops both cleanly. Backend on
`http://localhost:8000`, frontend on `http://localhost:3000`.

### Running each service by hand

Useful for debugging one side in isolation.

#### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # adjust if needed
uvicorn app.main:app --reload
```

Runs on `http://localhost:8000`. Data lives in `backend/data/` (gitignored —
never committed).

Run the parser test suite (all fixtures are fabricated, no real statement
data is ever checked into this repo):

```bash
pytest tests/
```

#### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at the backend above
npm run dev
```

Runs on `http://localhost:3000`. Open it, add an account, upload a
statement PDF, review the parsed transactions and categories, confirm
the import, then check the dashboard.

### Turning it into a clickable Mac app

No native build needed for the MVP — open `http://localhost:3000` in
Safari and "Add to Dock" (or use a wrapper like Unite/Fluid) to get an
icon that launches straight into the app.

## Roadmap

**Phase 2 — financial health tracking**
- Net worth is live (assets/liabilities, manual balance snapshots, MoM
  delta). Still open: savings rate, debt-to-income, retirement progress
  vs. a goal — the rest of the Optiml-inspired "health score" dashboard.
- A parser for bank/chequing statements (today only credit-card
  statements are supported), so income and day-to-day account balances
  stop needing manual entry.
- Multiple family members with their own login and permissions.

**Phase 3 — hosting & automation**
- Deploy backend + Postgres + frontend on TrueNAS via Docker Compose.
- Tailscale between TrueNAS, laptops, and phones — the app is reachable
  only over your private tailnet, never exposed to the public internet.
  This is the security boundary that makes it safe to stop being
  local-only.
- n8n (running alongside on TrueNAS) for automation: monthly reminders to
  upload a statement, a scheduled summary email, or watching a folder for
  new statement PDFs and calling `/statements/preview` automatically.
- Add authentication once more than one person / more than one device is
  using the app.

## Security notes

- Uploaded PDFs are processed in memory (`UploadFile.read()` → parser →
  discarded) and are never written to disk by the backend.
- The SQLite database and any `data/` directory are gitignored — nothing
  with real transactions or balances is ever committed.
- Parser tests use fabricated merchant names/dates/amounts, never a real
  statement, so the repo's history stays free of anyone's real financial
  data even in test fixtures.
