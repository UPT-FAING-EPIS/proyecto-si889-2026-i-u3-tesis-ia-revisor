# Repository Guidelines

## Project Structure & Module Organization

This repository contains a thesis-advisor web app with a Next.js frontend, FastAPI backend, and Supabase persistence. Frontend code lives in `frontend/app`, `frontend/components`, and `frontend/lib`; global styling is in `frontend/app/globals.css`. Backend code lives in `backend/app`, with API routes in `backend/app/routers`, service logic in `backend/app/services`, configuration in `backend/app/core`, and Supabase access in `backend/app/database`. SQL schema and migrations are under `backend/sql`. Documentation and diagrams are under `docs`.

## Build, Test, and Development Commands

Run the backend locally with:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend with:

```bash
cd frontend
npm install
npm run dev
```

Use `npm run build` in `frontend` to verify the production Next.js build. Use `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m py_compile backend/app/**/*.py` or compile specific changed files to catch Python syntax errors.

## Coding Style & Naming Conventions

Use 2-space indentation for JavaScript and JSX, and 4-space indentation for Python. React components use `PascalCase` filenames, for example `ThesisPlanPanel.jsx`; utility functions use `camelCase`. Python modules use `snake_case`, route files stay focused by feature, and Pydantic schemas belong in `backend/app/models/schemas.py`. Keep comments short and only where the code is not self-explanatory.

## Testing Guidelines

There is no formal test suite yet. Before submitting changes, run the frontend build and Python compile checks for modified backend files. For API work, exercise the affected endpoint through the local frontend or with authenticated requests. Name future tests by behavior, such as `test_thesis_plan_uses_selected_ai_provider`.

## Commit & Pull Request Guidelines

Recent commits use short conventional prefixes such as `feat:` followed by a Spanish or English summary. Keep that pattern, for example `feat: add DeepSeek model selection`. Pull requests should describe the user-facing change, list backend/frontend impact, mention required environment variables, and include screenshots for dashboard UI changes.

## Security & Configuration Tips

Never commit real API keys. Keep secrets in `backend/.env.local` or local environment variables, and keep examples placeholder-only in `backend/.env.example`. Required backend variables include `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY` or `API_GEMINI`, and `DEEPSEEK_API_KEY` when using DeepSeek.
