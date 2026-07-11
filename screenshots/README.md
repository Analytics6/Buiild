# Buiild Complaint RAG — Application Screenshots

Screenshots of the **Customer Support Intelligence** SPA (React + Vite frontend, FastAPI backend). Captured at **1440×900** desktop resolution unless noted.

## Screenshot Index

| File | Description | Auth / User |
|------|-------------|-------------|
| [01-login.png](./01-login.png) | Login page (logged out) — email/password form with “Customer Support Intelligence” branding | None |
| [02-dashboard.png](./02-dashboard.png) | Executive Overview dashboard — KPI cards, case volume trend, status mix pie chart, complaint drivers bar chart | `demo@support.ai` |
| [03-assistant-empty.png](./03-assistant-empty.png) | AI Complaint Assistant — empty state before starting a conversation | `demo@support.ai` |
| [04-assistant-new-review.png](./04-assistant-new-review.png) | AI Complaint Assistant — after clicking **New review** (active chat session, prompt template selector) | `demo@support.ai` |
| [05-reports.png](./05-reports.png) | Operational Reports — monthly metrics, resolution timeline, priority distribution charts | `demo@support.ai` |
| [06-knowledge-base.png](./06-knowledge-base.png) | Knowledge Base & Intake — JSON file upload area and priority cases table | `demo@support.ai` |
| [07-settings-demo.png](./07-settings-demo.png) | Application Settings — profile, OpenAI config, health info (manager role) | `demo@support.ai` |
| [08-settings-admin.png](./08-settings-admin.png) | Application Settings — same layout with **admin** role shown in profile | `admin@support.ai` |
| [09-mobile-dashboard.png](./09-mobile-dashboard.png) | Dashboard on mobile viewport (390×844) | `demo@support.ai` |

## Application Views (from `frontend/src/App.jsx`)

The app is a single-page application with state-based views (no React Router). All authenticated views share a common header and sidebar.

| View key | Sidebar label | Captured |
|----------|---------------|----------|
| `login` | — | ✅ `01-login.png` |
| `dashboard` | Dashboard | ✅ `02-dashboard.png`, `09-mobile-dashboard.png` |
| `assistant` | Assistant | ✅ `03-assistant-empty.png`, `04-assistant-new-review.png` |
| `reports` | Reports | ✅ `05-reports.png` |
| `knowledge` | Knowledge Base | ✅ `06-knowledge-base.png` |
| `settings` | Settings | ✅ `07-settings-demo.png`, `08-settings-admin.png` |

### Not captured (no distinct UI)

- **Admin panel** — no separate admin route; admin differs only by role text in Settings.
- **Sidebar Operations items** (Escalation queue, Resolution playbooks, Audit logs) — static labels, not navigable views.
- **Chat with AI response** — requires a live `/api/ask` call to OpenAI (slow/costly for batch screenshots).
- **Upload success message** — requires uploading a complaint JSON file during capture.

## Demo Credentials

| Email | Password | Role |
|-------|----------|------|
| `demo@support.ai` | `demo123` | manager |
| `admin@support.ai` | `admin123` | admin |

## How to Reproduce

### 1. Start the application

```powershell
# Terminal 1 — backend (port 8002, proxied by Vite)
cd c:\Users\Admin\Downloads\Buiild-main\Buiild-main
uvicorn backend.app.main:app --port 8002

# Terminal 2 — frontend (port 3000)
cd c:\Users\Admin\Downloads\Buiild-main\Buiild-main\frontend
npm run dev
```

Ensure `.env` exists at the project root with `OPENAI_API_KEY` set.

### 2. Install Playwright (one-time)

```powershell
pip install playwright
playwright install chromium
```

### 3. Run the capture script

```powershell
cd c:\Users\Admin\Downloads\Buiild-main\Buiild-main
python scripts/capture_screenshots.py
```

Screenshots are written to this folder. The script uses headless Chromium at `http://localhost:3000`.

### Manual capture

Open `http://localhost:3000` in a browser, sign in with the credentials above, and use the **Workspace** sidebar to switch views.

---

*Generated: 2026-07-11*
