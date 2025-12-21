# Imputable Deployment Guide

Production deployment guide for Imputable (The Decision Ledger).

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Vercel       │────▶│    Railway      │────▶│    Supabase     │
│   (Frontend)    │     │   (Backend)     │     │   (Database)    │
│   Next.js 14    │     │   FastAPI       │     │   PostgreSQL    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │
         │                      │
         ▼                      ▼
┌─────────────────┐     ┌─────────────────┐
│     Clerk       │     │     Stripe      │
│ (Authentication)│     │   (Billing)     │
└─────────────────┘     └─────────────────┘
```

---

## 1. Database (Supabase)

### Setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **Settings > Database** and copy the connection strings

### Required Connection Strings

Use the **Transaction Pooler** connection (port 6543) for the backend:

```
postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

### Environment Variable

```bash
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

---

## 2. Backend (Railway)

### Setup

1. Create a new project at [railway.app](https://railway.app)
2. Connect your GitHub repository
3. Set the root directory to `/decision_ledger` (if monorepo)
4. Railway auto-detects Python and uses the `Procfile`

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

# Application
ENVIRONMENT=production
SECRET_KEY=<generate-a-64-char-random-string>
ALLOWED_ORIGINS=https://your-app.vercel.app,https://imputable.vercel.app

# Clerk Authentication
CLERK_SECRET_KEY=sk_live_xxxxxxxxxxxx
CLERK_PUBLISHABLE_KEY=pk_live_xxxxxxxxxxxx

# Stripe Billing (for Enterprise features)
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx

# Optional: Alerting
SLACK_ALERTS_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx
```

### Generate SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Procfile

Ensure this file exists in your backend directory:

```
web: uvicorn decision_ledger.main:app --host 0.0.0.0 --port $PORT
```

### Health Check

After deployment, verify the backend is running:

```bash
curl https://your-backend.up.railway.app/health
# Expected: {"status": "healthy", ...}
```

---

## 3. Frontend (Vercel)

### Setup

1. Import your repository at [vercel.com](https://vercel.com)
2. Set the root directory to `/frontend`
3. Framework preset: **Next.js**

### Required Environment Variables

```bash
# API
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app/api/v1

# Clerk Authentication
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxxxxxxxxxxx
CLERK_SECRET_KEY=sk_live_xxxxxxxxxxxx

# Clerk Routing
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard
```

### Verify Deployment

1. Visit `https://your-app.vercel.app`
2. Sign in with Clerk
3. Navigate to `/dashboard` - should load without 401 errors

---

## 4. Clerk Authentication

### Setup

1. Create an application at [clerk.com](https://clerk.com)
2. Enable **Organizations** in the Clerk dashboard
3. Configure allowed redirect URLs:
   - `https://your-app.vercel.app/*`
   - `http://localhost:3000/*` (for development)

### Get API Keys

- **Dashboard > API Keys**
- Copy `Publishable Key` (starts with `pk_`)
- Copy `Secret Key` (starts with `sk_`)

### Enable Organizations

1. Go to **Organizations** in sidebar
2. Enable "Allow users to create organizations"
3. The frontend uses `<OrganizationSwitcher />` for multi-tenancy

---

## 5. Stripe Billing

### Setup

1. Create an account at [stripe.com](https://stripe.com)
2. Create Products and Prices for each tier:
   - **Starter**: $29/month
   - **Professional**: $99/month  
   - **Enterprise**: $299/month

### Environment Variables

```bash
STRIPE_SECRET_KEY=sk_live_xxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx

# Price IDs (optional, can also be stored in database)
STRIPE_STARTER_PRICE_ID=price_xxxxxxxxxxxx
STRIPE_PROFESSIONAL_PRICE_ID=price_xxxxxxxxxxxx
STRIPE_ENTERPRISE_PRICE_ID=price_xxxxxxxxxxxx
```

### Webhook Setup

1. Go to **Developers > Webhooks**
2. Add endpoint: `https://your-backend.up.railway.app/api/v1/webhooks/stripe`
3. Select events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`

---

## 6. Cron Jobs (Tech Debt Timer)

The expiry cron job processes decision review dates and sends notifications.

### Railway Cron

Add to `railway.toml`:

```toml
[cron]
  [[cron.jobs]]
    name = "expiry-check"
    schedule = "0 9 * * *"  # Daily at 9 AM UTC
    command = "python -m decision_ledger.jobs.expiry_cron"
```

### Manual Trigger

```bash
python -m decision_ledger.jobs.expiry_cron --database-url $DATABASE_URL
```

### Alerting

Set these environment variables for failure notifications:

```bash
# Slack alerts
SLACK_ALERTS_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx

# Or generic webhook (PagerDuty, Opsgenie)
ALERT_WEBHOOK_URL=https://events.pagerduty.com/v2/enqueue
```

---

## 7. Database Migration (REQUIRED)

Before launching, run this SQL to add billing columns:

```sql
-- Add subscription tier enum
DO $$ BEGIN
    CREATE TYPE subscription_tier AS ENUM ('free', 'starter', 'professional', 'enterprise');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add billing columns to organizations table
ALTER TABLE organizations 
ADD COLUMN IF NOT EXISTS subscription_tier subscription_tier NOT NULL DEFAULT 'free',
ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255);

-- Create index for Stripe customer lookup
CREATE INDEX IF NOT EXISTS idx_organizations_stripe_customer 
ON organizations(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
```

Run in Supabase SQL Editor or via migration tool.

---

## 8. Pre-Launch Security Checklist

### Critical Fixes Applied

- [x] **Data Leak Fixed**: All `get_decision()` calls now pass `organization_id`
- [x] **Stripe Bypass Prevented**: Subscription tier checked from database, not client
- [x] **Cron Alerting Added**: Job failures send Slack/webhook notifications
- [x] **Transaction Safety**: FastAPI session handles commit/rollback automatically

### Security Verification

- [ ] `SECRET_KEY` is unique and not committed to git
- [ ] `ALLOWED_ORIGINS` only includes your production domains
- [ ] Database password is strong and rotated periodically
- [ ] Stripe webhook secret is configured
- [ ] Dev login endpoint (`/auth/dev-login`) is disabled in production

### Functionality Testing

- [ ] Sign up flow works end-to-end
- [ ] Organization creation works
- [ ] Creating a decision works
- [ ] Amending a decision creates a new version (not overwrite)
- [ ] User A cannot access User B's decisions (test with different orgs)
- [ ] Audit export returns 402 for non-Enterprise users
- [ ] Risk dashboard returns 402 for non-Professional users

### Monitoring

- [ ] Railway logs are accessible
- [ ] Slack/webhook alerts are configured for cron failures
- [ ] Supabase dashboard shows active connections

---

## Environment Variables Summary

### Backend (Railway)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Supabase connection string (pooler) |
| `ENVIRONMENT` | Yes | `production` |
| `SECRET_KEY` | Yes | Random 64-char string for JWT signing |
| `ALLOWED_ORIGINS` | Yes | Comma-separated list of frontend URLs |
| `CLERK_SECRET_KEY` | Yes | Clerk secret key |
| `CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key |
| `STRIPE_SECRET_KEY` | No* | Stripe secret key (*required for billing) |
| `STRIPE_WEBHOOK_SECRET` | No* | Stripe webhook secret |
| `SLACK_ALERTS_WEBHOOK_URL` | No | Slack webhook for cron alerts |

### Frontend (Vercel)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key |
| `CLERK_SECRET_KEY` | Yes | Clerk secret key |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | Yes | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | Yes | `/sign-up` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` | Yes | `/dashboard` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` | Yes | `/dashboard` |

---

## Troubleshooting

### 401 Unauthorized on API calls

1. Check `CLERK_SECRET_KEY` is set on Railway
2. Check `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set on Vercel
3. Verify the token is being sent in `Authorization: Bearer <token>` header

### "Tenant or user not found" error

1. Use the **Transaction Pooler** URL (port 6543), not Direct (port 5432)
2. Verify database password is correct
3. Check Railway logs for connection errors

### CORS errors

1. Ensure `ALLOWED_ORIGINS` includes your Vercel domain
2. Don't include trailing slashes in origins
3. Restart the Railway deployment after changing

### Audit Export returns 402

This is expected! The audit export feature requires an Enterprise subscription. To test:
1. Set up Stripe with a test subscription
2. Or set `ENVIRONMENT=development` to bypass checks temporarily

---

## Support

For issues, open a GitHub issue or contact support@imputable.io
