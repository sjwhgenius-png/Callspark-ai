# CallSpark AI Frontend

Professional React + Vite frontend for an HVAC AI receptionist product.

## Includes
- polished SaaS-style landing/app shell
- dashboard cards and analytics
- lead pipeline table
- conversation inbox
- workflow and settings pages
- mock data by default
- optional backend connection with `VITE_API_BASE_URL`

## Run locally

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Connect backend

Create a `.env` file:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

The app will try to fetch a daily snapshot from:

```text
/internal/report/daily
```

If the backend is unavailable, the app falls back to built-in demo data.

## Deploy
- Frontend: Vercel
- Backend: Render or Railway
- Database: Supabase
- Messaging: Twilio.
