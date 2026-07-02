# AssetIQ — Phase 05: Automation (Telegram → Gemini → Google Calendar)

**Track:** Automation
**Depends on:** 00 (`BookingIn`, `bookings` table, `.env` keys), 03 (`BookingDispatcher` protocol).
**Gate:** none

## Objective

Turn a confirmed inspection booking into a real calendar event: send the request to Telegram, wait
for a human confirmation, then a **Gemini** agent books it on Google Calendar — with a deterministic
fallback that works with no LLM/calendar keys.

## Consumes

- `BookingDispatcher` protocol from Phase 03 (real implementation lives here).
- `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`,
  `GOOGLE_CALENDAR_CREDENTIALS_JSON`, `GOOGLE_CALENDAR_ID`. Secrets never printed.

## Produces

- `services/telegram_bot.py` — `TelegramDispatcher(BookingDispatcher)`.
- `services/calendar_agent.py` — Gemini agent + deterministic fallback.

## Flow

1. `POST /booking` (Phase 03) persists a `bookings` row and calls the configured dispatcher.
2. **`TelegramDispatcher`** formats and sends a message with **Name, Nearest Mercedes Workshop, Car
   model, Purpose, Date, Time**; sets status `sent`, stores `telegram_message_id`. Watches replies
   via **long-polling** (no public webhook needed) for a confirmation ("confirmed"/"approved"/etc.).
   > **TODO(P05):** decide the polling runtime — FastAPI background task vs. a separate worker process — and how the Telegram update offset is persisted so confirmations aren't missed/double-processed across restarts.
   > **TODO(P05):** resolve the "Nearest Mercedes Workshop" source (see cross-cutting TODO in the overview) before formatting the message — real curated list vs. user-supplied.
3. On confirmation → status `confirmed` → invoke **`calendar_agent`**.
4. **`calendar_agent`**:
   - **Gemini path** (keys present): the model interprets the free-text confirmation, extracts the
     booking intent, and creates the event via **Google Calendar API**; status `booked`, store
     `calendar_event_id`.
     > **TODO(P05):** pin the Gemini model id and define the extraction prompt + structured output schema (fields to extract, refusal/ambiguity handling so a non-confirmation never books).
   - **Deterministic fallback** (no Gemini key, or Gemini unavailable): build the event directly
     from the structured `bookings` row and create it via the Calendar API.
     > **TODO(P05):** define the Google Calendar event template — event duration, timezone (`Asia/Kuala_Lumpur`), location (from the workshop), title/description format, and attendee/reminder settings. Shared by both the Gemini and deterministic paths.
   - **Dry-run** (no Google keys): status `dry_run`, log the event payload it *would* create.

## Safety / robustness
- Missing any key → degrade to the next fallback tier; never crash `POST /booking`.
- Confirmation detection is explicit (keyword/allow-list), not guessed, so a random reply can't
  trigger a booking.
  > **TODO(P05):** finalize the confirmation keyword allow-list, casing/locale handling, and whether the reply must come from a specific authorised chat/user id.
- All secrets read via `Settings`; never logged or echoed in responses.

## Tests (PyTest — all external calls mocked)
- Message formatting includes all six required fields, correctly labelled.
- Confirmation detection: accepts "confirmed"/"approved", rejects unrelated text.
- Gemini path (mocked SDK) → Calendar create called with correct event; status `booked`.
- Deterministic fallback (no Gemini key) builds the same event from structured data.
- Dry-run (no Google keys) returns payload, status `dry_run`, makes no external call.
- No secret string appears in logs/return values.

## Done criteria
- With keys: booking → Telegram message → confirmation reply → Google Calendar event created.
- Without keys: full pipeline runs in fallback/dry-run without errors and is fully unit-tested.
- Swappable into Phase 03 by config (replaces `DryRunDispatcher`).
