# Imputable

**Imputable** — A system of record for engineering and product decisions with immutable versioning, audit trails, and approval workflows.

## Features

- **Immutable Versioning**: Decisions are never modified in place. Every edit creates a new version.
- **Audit Trail**: Complete history of who viewed, modified, and approved each decision.
- **Tech Debt Timer**: Track temporary decisions with review dates and expiry alerts.
- **Risk Dashboard**: Executive view of expiring and at-risk decisions.
- **Audit Export**: One-click SOC2/ISO/HIPAA compliant PDF reports.

## Tech Stack

- **Backend**: FastAPI + PostgreSQL + SQLAlchemy (async)
- **Frontend**: Next.js 14 + TypeScript + Tailwind CSS

## Quick Start

```bash
# Install backend dependencies
python3 -m venv venv
source venv/bin/activate
pip install -e .

# Set up database
createdb imputable
python seed_data.py

# Run backend
uvicorn decision_ledger.main:app --reload --port 8000

# Run frontend (in another terminal)
cd frontend
npm install
npm run dev
```

## Environment Variables

Create a `.env` file in the root directory:

```env
DATABASE_URL=postgresql://user@localhost:5432/imputable
ALLOWED_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

## License

MIT
