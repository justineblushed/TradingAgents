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
- **Category drill-down** (`/categories/<name>`): click any bar in the
  dashboard's Category Breakdown (or a category name on the Categories
  page) to see every transaction behind it, the month's total, how that
  compares to the category's own typical month and to its budget, and a
  12-month trend you can click to jump between months. The drill-down
  total is computed the same way the chart is — transfers excluded,
  refunds netted — so the two can never disagree. Empty months are
  labelled as "no statement imported", which is not the same claim as
  "spent nothing".
- **Category colour and emoji**: every category carries its own colour and
  optional emoji, editable on the Categories page. Hue tracks the group
  (Housing indigo, Food green, Transportation cyan …) and shade separates
  categories within it, so the pie reads at a glance. Deliberately not a
  rotating chart palette — a colour has to mean the same category
  everywhere, or "the blue slice" changes meaning whenever spending
  reorders the chart.
- **Auto-categorization rules** (`/rules` page): a rule fires when its
  keyword appears in the description, optionally narrowed by an amount
  range and/or a specific account — so the same merchant can mean two
  things (a small annual membership fee vs. a big grocery run) and land in
  the right place. When several rules match, the most specific wins, with
  an explicit priority as the tie-breaker. A rule can also attach tags.
  Rules can be re-run over transactions already imported, always with a
  preview first and a scope that defaults to touching only uncategorized
  rows. Categories set by hand are recorded as such and left alone unless
  you explicitly ask for the widest scope — a bulk re-file should never
  silently undo a correction.
- **Coming up** card on the dashboard: the next payday, projected from the
  cadence of the pay stubs entered, and the recurring bills due in the next
  30 days. Both are *inferred*, not scheduled — a charge only appears once
  it has repeated at least three times on a steady enough rhythm, and each
  row shows the evidence behind it. Amounts that move between cycles are
  shown as a range rather than a single confident number.
- **Cash Flow Sankey** (`/cash-flow`): income sources flow into a hub, then
  out to spending groups and their categories, plus whatever's left over
  to Savings. Node colours are the same ones used everywhere else in the
  app, and clicking a category opens its drill-down. A group with only
  one populated category that month is drawn as a single node rather than
  a group and an identical-looking leaf underneath it. When spending
  exceeds income, there's no fabricated flow into savings — a
  negative-value link isn't meaningful in a Sankey — the gap is reported
  as a number instead.
- **Sign Check** (`/sign-check`): finds transactions filed under an income
  category (Employment Income, Rental Income, ...) but stored with a
  positive amount instead of the negative this app's convention expects.
  One of these doesn't just look odd on its own — it drags the income
  total on the Dashboard, Cash Flow, and that category's drill-down
  toward zero or negative, since all three negate a category's raw total
  to show it as a positive number. Usually left over from a statement
  imported before a CSV's sign convention was reconciled, or a manual
  recategorization onto a row whose amount didn't get reconsidered.
  Dashboard and Cash Flow show a banner linking here whenever their
  income figure is actually negative; each flagged row can be fixed
  individually or in bulk, and the fix re-validates every row itself
  rather than trusting a stale list.
- **Spending Calendar** (`/calendar`): a month grid shaded by that day's
  spending, scaled against the month's own highest-spending day rather
  than a fixed dollar amount, so a quiet month and a big one both use the
  full range of shading. A green dot marks a day money came in. The grid
  always starts on Monday and ends on Sunday, so a few days from the
  adjacent month pad the front/back — those days keep their real
  transaction data (a padding-day purchase isn't hidden or zeroed) but are
  visually dimmed and excluded from the month's own totals, which are
  computed the same way as the Dashboard's so the two can never disagree.
  Clicking any day, including a padding one, opens its transactions inline
  and links through to the Transactions page filtered to that month.
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
- **Payroll & tax** (`/payroll`): a bank statement only shows the net
  deposit, which hides everything you actually paid. Pay stubs are
  uploaded (best-effort PDF read, every field editable before saving) or
  entered by hand, capturing gross pay, income tax, CPP, EI, RRSP,
  pension and union dues. From those it derives an annualized income
  (using the stubs' own pay cadence, not an assumed biweekly), your
  marginal and average tax rate, the federal/provincial brackets you sit
  in, whether withholding is running ahead or behind, and estimated RRSP
  room including the tax saving from contributing the remainder.
  Tax rates are **data, not code**: `tax_brackets` / `tax_year_settings`
  are seeded with 2025 federal + Manitoba figures and edited in the app,
  since the CRA indexes them annually. Every derived figure is labeled an
  estimate with a "verify against canada.ca" note — it can't see other
  income, credits beyond the basic personal amount, spousal transfers, or
  your CRA carry-forward (which you can enter from your NOA).
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

CSV exports are auto-detected (`csv_statement.py`), including headerless
bank exports and ledger-style Funds Out/In columns. One ambiguity worth
knowing about: a single signed "Amount" column doesn't say which sign
convention it uses. Credit-card exports are almost always
positive-for-charge (matching this app's own convention); many
chequing/savings exports — Simplii among them — sign it the opposite way,
negative for a withdrawal. Since "Amount" alone can't distinguish the
two, the parser leans on the fact that spending transactions vastly
outnumber deposits in any real statement: if most of a file's raw values
come out negative, it flips every sign so spending reads positive here
too, and says so in the preview warnings rather than doing it silently.

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
