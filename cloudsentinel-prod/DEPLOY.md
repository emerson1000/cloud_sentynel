# CloudSentinel — Guía de Despliegue a Producción

## Estructura del proyecto
```
cloudsentinel/
├── frontend/          ← Next.js 14 → despliega en Vercel (gratis)
├── backend/           ← FastAPI + Azure Functions → Azure Container Apps
│   ├── core/          ← Analyzers (Azure/AWS/GCP), DB, Notifications
│   ├── functions/     ← Scheduled jobs (daily check + weekly report)
│   ├── api.py         ← REST API que consume el frontend
│   ├── Dockerfile
│   └── requirements.txt
├── .github/workflows/ ← CI/CD automático al hacer push a main
└── infra/             ← Scripts de infraestructura Azure
```

---

## PASO 1 — Supabase (Base de datos + Auth)

### 1.1 Crear proyecto
1. Ve a https://supabase.com → New Project
2. Guarda: **URL**, **anon key**, **service_role key**

### 1.2 Crear el schema de base de datos
1. En tu proyecto Supabase → SQL Editor
2. Pega y ejecuta el contenido de `backend/core/database_multicloud.py` → sección `SCHEMA_SQL`

### 1.3 Configurar Auth
1. Authentication → Settings
2. Site URL: `https://app.cloudsentinel.io`
3. Redirect URLs: `https://app.cloudsentinel.io/auth/callback`
4. (Opcional) Desactiva "Confirm email" para desarrollo más rápido

---

## PASO 2 — Frontend en Vercel

### 2.1 Instalar Vercel CLI y subir
```bash
cd frontend
npm install
npm run build   # verifica que compila sin errores

npm install -g vercel
vercel login
vercel --prod
```

### 2.2 Variables de entorno en Vercel Dashboard
1. Ve a Vercel Dashboard → tu proyecto → Settings → Environment Variables
2. Agrega estas variables (obtén los valores de Supabase):

```
NEXT_PUBLIC_SUPABASE_URL      = https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY = eyJhbGci...
NEXT_PUBLIC_API_URL           = https://cloudsentinel-api.azurecontainerapps.io
NEXT_PUBLIC_APP_URL           = https://app.cloudsentinel.io
```

**Nota de seguridad:** Nunca subas archivos `.env*` a GitHub. Usa `.env.example` como plantilla y configura las variables en Vercel Dashboard.

### 2.3 Dominio personalizado (opcional)
Vercel Dashboard → Domains → Add `app.cloudsentinel.io`

---

## PASO 3 — Backend en Azure

### 3.1 Crear recursos Azure (ejecutar una vez)
```bash
az login

# Grupo de recursos
az group create --name cloudsentinel-rg --location eastus

# Azure Container Registry (para guardar la imagen Docker)
az acr create --resource-group cloudsentinel-rg \
  --name cloudsentinelacr --sku Basic --admin-enabled true

# Container App Environment
az containerapp env create \
  --name cloudsentinel-env \
  --resource-group cloudsentinel-rg \
  --location eastus

# Storage para Azure Functions
az storage account create \
  --name cloudsentinelstorage \
  --resource-group cloudsentinel-rg \
  --sku Standard_LRS

# Function App (para los scheduled jobs)
az functionapp create \
  --resource-group cloudsentinel-rg \
  --consumption-plan-location eastus \
  --runtime python --runtime-version 3.11 \
  --functions-version 4 \
  --name cloudsentinel-functions \
  --storage-account cloudsentinelstorage \
  --os-type linux
```

### 3.2 Generar la encryption key
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Guarda el resultado — lo necesitas en los pasos siguientes
```

### 3.3 Build y deploy de la API (Docker → Container Apps)
```bash
cd backend

# Build image
az acr build \
  --registry cloudsentinelacr \
  --image cloudsentinel-api:latest .

# Deploy como Container App
az containerapp create \
  --name cloudsentinel-api \
  --resource-group cloudsentinel-rg \
  --environment cloudsentinel-env \
  --image cloudsentinelacr.azurecr.io/cloudsentinel-api:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 --max-replicas 3 \
  --env-vars \
    SUPABASE_URL=secretref:supabase-url \
    SUPABASE_SERVICE_KEY=secretref:supabase-service-key \
    SUPABASE_ANON_KEY=secretref:supabase-anon-key \
    CLOUDSENTINEL_ENCRYPTION_KEY=secretref:encryption-key \
    RESEND_API_KEY=secretref:resend-key \
    TELEGRAM_BOT_TOKEN=secretref:telegram-token \
    FRONTEND_URL=https://app.cloudsentinel.io
```

### 3.4 Deploy de Azure Functions (scheduled jobs)
```bash
cd backend/functions

# Instalar Azure Functions Core Tools
npm install -g azure-functions-core-tools@4

# Configurar variables de entorno
az functionapp config appsettings set \
  --name cloudsentinel-functions \
  --resource-group cloudsentinel-rg \
  --settings \
    SUPABASE_URL="https://xxxx.supabase.co" \
    SUPABASE_SERVICE_KEY="eyJhbGci..." \
    CLOUDSENTINEL_ENCRYPTION_KEY="tu-fernet-key" \
    RESEND_API_KEY="re_xxx" \
    RESEND_FROM_EMAIL="alerts@cloudsentinel.io" \
    TELEGRAM_BOT_TOKEN="123:ABC"

# Deploy
func azure functionapp publish cloudsentinel-functions
```

---

## PASO 4 — CI/CD con GitHub Actions

### 4.1 Configurar secrets en GitHub
Ve a tu repo → Settings → Secrets → Actions → New repository secret:

```
NEXT_PUBLIC_SUPABASE_URL       → tu URL de Supabase
NEXT_PUBLIC_SUPABASE_ANON_KEY  → tu anon key
NEXT_PUBLIC_API_URL            → URL del Container App
VERCEL_TOKEN                   → vercel.com → Settings → Tokens
VERCEL_ORG_ID                  → vercel.com → Settings → General
VERCEL_PROJECT_ID              → en tu proyecto Vercel → Settings
AZURE_CREDENTIALS              → ver paso 4.2
ACR_LOGIN_SERVER               → cloudsentinelacr.azurecr.io
ACR_USERNAME                   → (de az acr credential show)
ACR_PASSWORD                   → (de az acr credential show)
```

### 4.2 Crear Service Principal para GitHub Actions
```bash
az ad sp create-for-rbac \
  --name "cloudsentinel-github-actions" \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/cloudsentinel-rg \
  --sdk-auth
# Pega el JSON completo como AZURE_CREDENTIALS en GitHub Secrets
```

### 4.3 Flujo de deploy automático
A partir de aquí, **cada `git push` a `main`** despliega automáticamente:
- Frontend → Vercel (build + deploy)
- Backend API → Azure Container Apps (build Docker + deploy)
- Azure Functions → Function App (deploy directo)

---

## PASO 5 — Usuario demo para pruebas

```sql
-- Ejecutar en Supabase SQL Editor después del primer deploy
-- Crea una cuenta demo que cualquiera puede usar para probar

INSERT INTO auth.users (id, email, encrypted_password, email_confirmed_at, created_at, updated_at)
VALUES (
  gen_random_uuid(),
  'demo@cloudsentinel.io',
  crypt('demo1234', gen_salt('bf')),
  NOW(), NOW(), NOW()
);
```

---

## Costos estimados en producción

| Servicio | Tier | Costo/mes |
|---|---|---|
| Vercel | Hobby (free) | $0 |
| Supabase | Free (500MB DB) | $0 |
| Azure Container Apps | Consumption (scale to 0) | ~$2–5 |
| Azure Functions | Consumption (1M calls gratis) | $0 |
| Azure Container Registry | Basic | $5 |
| Resend | Free (3k emails) | $0 |
| **Total MVP** | | **~$5–10/mes** |

---

## URLs finales de producción
- Frontend:       https://app.cloudsentinel.io  (Vercel)
- API:            https://cloudsentinel-api.azurecontainerapps.io
- Supabase:       https://xxxx.supabase.co
- Azure Functions: cloudsentinel-functions (interno)
