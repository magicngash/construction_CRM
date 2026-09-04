# Construction CRM — Project Context

Last updated: 2026-09-03

## Purpose

A small construction business operating system for managing projects, money, materials, labour, site reports, payroll, and an AI assistant.

## Current architecture

- Frontend: Streamlit in `frontend.py`
- Backend: FastAPI in `backend/main.py`
- Data/API models: `backend/schemas.py`
- Supabase client/database setup: `backend/database.py`
- Default backend URL used by the frontend: `http://localhost:8000`
- Frontend can override the backend URL with `SITEMGR_API_BASE`.

## Features currently implemented

- Dashboard with project filtering, budget position, spending by category, recent transactions, worker count, and low-stock materials.
- Project creation, editing, deletion, status, budget, location, and notes.
- Transaction recording and transaction history.
- Receipt/file uploads to Supabase Storage.
- Materials inventory with stock levels and low-stock thresholds.
- Material movements for received/used stock, including audit fields.
- Labour records and daily attendance with days worked and advances.
- Site reports with work completed, headcount, issues, materials consumed, and photo URLs.
- AI Assistant endpoint using DeepSeek and live CRM context.
- Weekly labour payroll workflow:
  - seven-day payroll preview;
  - payroll generation;
  - approval;
  - payment recording;
  - payment transaction creation.
- New material-control workflows:
  - delivery receiver/checker, condition, event date, and evidence fields;
  - issuance recipient and work-area accountability fields;
  - daily stock book-balance calculation;
  - physical stock audits with variance flags and sign-off fields;
  - discrepancy records for investigation.
- New labour workflows:
  - worker type, contact, pay period, and attendance sign-off fields;
  - piece-work/subcontractor logging with verification status;
  - verified piece-work included in payroll calculations.

## Important backend endpoints

- `GET /health`
- `GET /projects`
- `POST/PATCH/DELETE /projects...`
- `GET/POST /transactions`
- `GET/POST /materials`
- Material movement endpoints
- Labour and attendance endpoints
- Site report endpoints
- `POST /uploads`
- `GET /dashboard/summary`
- `POST /ai/ask`
- `GET /labor/payroll/preview`
- `GET/POST /labor/payroll`
- `POST /labor/payroll/{payroll_id}/approve`
- `POST /labor/payroll/{payroll_id}/pay`

## Configuration

Backend environment variables expected by the code include Supabase connection settings and, for the AI assistant, `DEEPSEEK_API_KEY`. The AI endpoint returns a configuration error if the DeepSeek key is missing.

## Known notes / follow-up checks

- This folder is not currently a Git repository, so there is no commit history or diff to use as a checkpoint.
- Some emoji characters displayed as mojibake during terminal inspection; verify the UI encoding in the browser.
- The app should be run and tested end-to-end with the backend, Supabase tables, storage bucket, and frontend together.
- Confirm the Supabase schema contains the payroll table and the `source_payroll_id` transaction field expected by the payroll payment flow.
- Confirm the DeepSeek model name/API behavior before relying on the AI Assistant in production.
- Run `supabase_material_labor_upgrade.sql` in the Supabase SQL Editor before using the new fields/endpoints.

## How to resume in a future chat

Tell the assistant:

> Read `PROJECT_CONTEXT.md` first, inspect the current files, and continue from the outstanding follow-up checks. Do not discard existing changes.
