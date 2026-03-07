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

## Quick Start (desarrollo local)

```bash
# 1. Clonar
git clone https://github.com/tu-usuario/cloudsentinel
cd cloudsentinel

# 2. Frontend
cd frontend
cp .env.local.example .env.local
# → Edita .env.local con tus keys de Supabase
npm install
npm run dev
# Abre http://localhost:3000

# 3. Backend
cd ../backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# → Edita .env con tus variables
uvicorn api:app --reload --port 8000
```

## Deploy a producción

Ver [DEPLOY.md](./DEPLOY.md) para instrucciones completas paso a paso.

---

## Estructura del proyecto

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

## Licencia
MIT
