# Assistant Dashboard (Next.js)

Private admin dashboard for the WhatsApp AI Assistant.

## Stack
- Next.js 14 (App Router) + React 18
- TailwindCSS
- Talks to the FastAPI backend via `/api/*` (rewritten to `NEXT_PUBLIC_API_URL`)

## Develop
```bash
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm install
npm run dev                         # http://localhost:3000
```

## Structure
```
src/
  app/
    layout.tsx      # root layout
    page.tsx        # Overview dashboard (auth-gated)
    login/page.tsx  # login form -> JWT stored client-side
  components/
    Sidebar.tsx     # navigation across all feature sections
  lib/
    api.ts          # typed API client (JWT bearer)
```

The sidebar enumerates the full feature set (Overview, Conversations, Memory,
Search, Notes, Tasks, Calendar, Files, Analytics, Prompt Manager, Models,
Settings, Logs, Health, API Usage); Overview, Login, and Tasks are wired to the
backend, and remaining sections follow the same client pattern.
