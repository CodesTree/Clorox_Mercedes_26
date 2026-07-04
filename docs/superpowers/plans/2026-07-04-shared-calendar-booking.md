# Shared Calendar Booking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align booking integration with Phase 05 by creating inspection bookings in a shared Mercedes/AssetIQ Google Calendar using service-account credentials.

**Architecture:** Keep the current Phase 03 FastAPI backend intact. Replace the user-OAuth booking flow with a shared-calendar dispatcher that creates calendar events when service-account credentials are configured, and falls back to dry-run booking when credentials are absent or calendar creation fails.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Google Calendar API service-account credentials.

---

### Task 1: Shared Calendar Contract

**Files:**
- Modify: `backend/tests/test_google_calendar_booking.py`
- Modify: `frontend/src/api/client.test.ts`

- [ ] Write failing tests for shared calendar event payloads, dry-run fallback, successful event creation, and frontend booking response parsing.
- [ ] Run the focused tests and confirm they fail against the old user-OAuth implementation.

### Task 2: Backend Implementation

**Files:**
- Modify: `backend/app/services/google_calendar.py`
- Modify: `backend/app/services/booking.py`
- Modify: `backend/app/routers/booking.py`
- Modify: `backend/app/main.py`
- Delete: `backend/app/routers/google_auth.py`

- [ ] Implement service-account calendar event creation.
- [ ] Replace the OAuth dispatcher with `SharedCalendarDispatcher`.
- [ ] Remove `/auth/google/*` routes.
- [ ] Preserve `/booking` response payloads so the frontend can show calendar-created or dry-run state.

### Task 3: Frontend Client Cleanup

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] Remove user OAuth helper functions.
- [ ] Keep `createBooking` and shared calendar payload types.

### Task 4: Configuration and Verification

**Files:**
- Modify: `.env.example`
- Modify: `backend/requirements.txt`

- [ ] Keep shared calendar env vars only.
- [ ] Run backend tests, frontend tests, and frontend build.
