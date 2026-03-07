# ⚡ CloudSentinel

**Multi-cloud cost intelligence for startups and agencies.**  
Detect zombie resources, spending anomalies and optimization opportunities across Azure, AWS and GCP.

---

## Stack

| Layer | Tech | Hosting |
|---|---|---|
| Frontend | Next.js 14 (App Router) + Tailwind | Vercel |
| Auth | Supabase Auth (JWT) | Supabase |
| Database | PostgreSQL (Supabase) | Supabase |
| API | FastAPI (Python) | Azure Container Apps |
| Scheduled jobs | Azure Functions (Python timers) | Azure |
| Email | Resend | SaaS |
| Alerts | Telegram Bot API | SaaS |

---

## Quick Start (local development)

```bash
# 1. Clone
git clone https://github.com/tu-usuario/cloudsentinel
cd cloudsentinel

# 2. Frontend
cd frontend
cp .env.local.example .env.local
# → Edit .env.local con tus keys de Supabase
npm install
npm run dev
# open http://localhost:3000

# 3. Backend
cd ../backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# → Edita .env con tus variables
uvicorn api:app --reload --port 8000
```

## Deploy to production

see [DEPLOY.md](./DEPLOY.md) for complete instructions step by step

---

# Scan System Patch

## Files to update in GitHub

### 1. backend/api.py
Replace with the new api.py (was api_v2.py). Adds:
- GET  /api/scan/quota         → returns weekly usage
- POST /api/scan/{id}          → on-demand scan with quota enforcement
- POST /api/connections        → auto-triggers first scan in background

### 2. frontend/src/components/ui/ScanButton.tsx
Replace with new version. Shows:
- "1/2 this week · resets 2026-03-09" under the button
- Button disabled + grayed when limit reached
- Free users see lock icon + "Upgrade" link

### 3. Run in Supabase SQL Editor
backend/migrations/002_scan_quota.sql

## Scan rules
| Tier       | Weekly on-demand scans | Auto (Monday) |
|------------|----------------------|---------------|
| free       | 0 (locked)           | ✅            |
| pro        | 2                    | ✅            |
| enterprise | unlimited            | ✅            |

## First scan
When a user connects their first cloud account, a scan runs automatically
in the background (no quota consumed). User sees dashboard right away.
---


## Structure Project

```
cloudsentinel/
├── frontend/
│   ├── src/
│   │   ├── app/                  ← Next.js App Router pages
│   │   │   ├── (landing)/        ← Página pública de marketing
│   │   │   ├── auth/             ← login, register, callback
│   │   │   ├── onboarding/       ← Flujo de conexión cloud
│   │   │   └── dashboard/        ← Workspace del usuario
│   │   ├── components/
│   │   │   ├── ui/               ← KpiCard, ZombieRow, ScanButton, etc
│   │   │   ├── charts/           ← SpendChart, ServiceDonut
│   │   │   └── layout/           ← SidebarNav, TopBar
│   │   └── lib/
│   │       ├── supabase/         ← client.ts + server.ts
│   │       └── api.ts            ← Todos los calls al backend
│   ├── middleware.ts              ← Protección de rutas
│   └── vercel.json
│
├── backend/
│   ├── core/
│   │   ├── base_analyzer.py      ← Interfaz abstracta + factory
│   │   ├── azure_analyzer.py     ← Azure SDK implementation
│   │   ├── aws_analyzer.py       ← boto3 implementation
│   │   ├── gcp_analyzer.py       ← Google Cloud SDK implementation
│   │   ├── database_multicloud.py ← Supabase operations
│   │   └── notifications.py      ← Resend email + Telegram
│   ├── functions/
│   │   └── function_app.py       ← Azure Functions timers
│   ├── api.py                    ← FastAPI REST endpoints
│   ├── Dockerfile
│   └── requirements.txt
│
├── .github/workflows/
│   └── deploy.yml               ← CI/CD automático
│
└── DEPLOY.md                    ← Guía de despliegue completa
```

---

## MIT LICENCE

