# Quantly frontend

React + TypeScript + Vite + Tailwind. Talks to the Quantly API, uploads holdings
CSVs, polls for the async analysis, and renders the results (stat tiles, an
equity curve via Lightweight Charts, risk insight cards, and a correlation
heatmap).

## Setup

```sh
npm install
cp .env.example .env   # adjust if the API is not on localhost:8000
npm run dev            # http://localhost:5173
```

## Scripts

- `npm run dev` — dev server with HMR
- `npm run build` — type-check then production build
- `npm run lint` — oxlint
- `npm run preview` — serve the production build

## Configuration

Set via `.env` (see `.env.example`):

- `VITE_API_URL` — base URL of the API (default `http://localhost:8000`)
- `VITE_GOOGLE_CLIENT_ID` — optional; when set, shows the Google sign-in button

## Structure

```
src/
  components/   reusable UI (cards, charts, layout, auth)
  lib/          api client, auth, query hooks, types, formatting
  pages/        routed pages (auth, portfolios list, upload, detail)
  router.tsx    route table (public auth routes + protected app routes)
```
