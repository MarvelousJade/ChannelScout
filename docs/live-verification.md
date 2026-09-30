# Local Docker and live Telegram verification

This extends the earlier verification records; their Docker/Telegram blockers were accurate at the time. No deployment, production load, hosted CI or GitHub push is claimed.

## Observations before the snippet fix

- Windows Docker Engine 29.6.1 became reachable through `docker.exe`; the WSL `/var/run/docker.sock` connection remains unavailable.
- Image built successfully with Python 3.12.14, PTB 22.8 and psycopg 3.3.6. PostgreSQL container: 18.6 (Debian 18.6-1.pgdg13+2), x86_64.
- Windows refused binding localhost:8000. An ignored `.local/compose-port.yaml` override exposes localhost:18000 instead; no unrelated process was stopped and no OS networking settings changed.
- Real HTTP `/health` and `/ready` returned alive/ready. The first container suite passed 48 tests against a separate `scout_container_test` DB, never the live `scout` DB. Warnings: existing Starlette TestClient deprecation and a non-root pytest cache permission warning (tests still passed).
- The user added the bot to a controlled public demo channel and posted a resource. Bot membership/API connectivity was checked. The user then reported a live private-bot search result with the correct source date/channel/link, demonstrating the end-to-end flow. Database inspection confirmed the approved post and two sent replies with zero failed replies at that observation (start/help and search are not assumed to be exactly-once deliveries).
- The user-reported snippet was `,Python, ,async, tutorial with coroutine examples`. Source text was `Python async tutorial with coroutine examples` with no commas. This is a real local demo formatting defect, not one of the deliberately introduced debugging exercises. The user reported the output; diagnosis and fixes below are agent-performed.

## Snippet repair acceptance criteria (before implementation)

- [x] Add and run failing regressions asserting exact short snippets, including a source with intentional punctuation.
- [x] Correct the headline option encoding without stripping legitimate commas, changing search ranking, or introducing Telegram markup.
- [x] Rerun the full container suite, lint/format and health/readiness after rebuilding; preserve the live post and pending/sent reply data.
- [x] Inspect and commit only relevant code/tests/documentation using the user's configured identity; never commit .env or push.
- [x] Ask for a new live search and verify post-fix rendering. The user reported clean/edited snippets and later a successful live Next/Previous round-trip.

## Root-cause experiment

Run through the Docker PostgreSQL container, on literal test text (not by altering live data):

```sql
SELECT ts_headline('english', 'Python async tutorial with coroutine examples',
                  plainto_tsquery('english', 'python async'),
                  'StartSel=, StopSel=, MaxWords=20, MinWords=8');
-- Observed: ,Python, ,async, tutorial with coroutine examples

SELECT ts_headline('english', 'Python async tutorial with coroutine examples',
                  plainto_tsquery('english', 'python async'),
                  'StartSel="", StopSel="", MaxWords=20, MinWords=8');
-- Observed: Python async tutorial with coroutine examples
```

The unquoted empty marker options were parsed as comma marker strings. Explicit quoted empty values suppress highlight markers while preserving source punctuation. A global comma replacement would hide the symptom but corrupt real content. Bot replies remain plain text; no HTML/Markdown parsing is added.

## Fix and final checks

Before changing production SQL, both new exact-snippet regressions failed (**2 failed in 6.12s**). One used plain text; the other contained intentional commas/colon/parentheses, rejecting a destructive punctuation-strip workaround.

Fixed `StartSel` and `StopSel` by explicitly quoting their empty values in the option string. Afterward: **50 passed in 15.64s** on the native PostgreSQL setup; lint/format passed. Rebuilt/restarted only the app container, retaining its database volume, then **50 passed in 11.85s** in Python 3.12.14 against the isolated container test DB. Disabled pytest's cache provider for that read-only/non-root image; the existing Starlette warning remains.

Real HTTP health/readiness passed again on port 18000. A read-only call to the rebuilt search module returned the exact clean snippet for the existing live demo post. Original post identity/text were preserved and polling remains enabled. The user subsequently sent another search and reported the clean snippet, confirming post-fix live rendering. Previously saved snapshots deliberately retain their prior snippet.

## Reproduction and runtime commands

This machine uses Windows `docker.exe`; Linux `docker` does not reach Desktop's socket. The ignored local override is:

```yaml
services:
  scout:
    ports: !override
      - "127.0.0.1:18000:8000"
```

```sh
docker.exe compose -f compose.yaml -f .local/compose-port.yaml up --build -d
curl.exe -f http://127.0.0.1:18000/health
curl.exe -f http://127.0.0.1:18000/ready
```

For container tests, create a separate disposable database and set TEST_DATABASE_URL to it. In the test child process set MODE=off and clear TELEGRAM_TOKEN/ALLOWED_CHAT_IDS, leaving the running polling service's environment unchanged. Run `pytest -q -p no:cacheprovider`. Never point fixtures at the live DB. Credentials and `.local` runtime artifacts remain ignored and were not committed.

## Live edit verification

The user edited the same channel post from `Python async tutorial with coroutine examples` to `Python async tutorial with cancellation examples`, then searched `/search python async cancellation`. They reported the new snippet, unchanged posting date (2026-09-30), and the same original-message link ending `/4`.

A read-only database/search check confirmed one row for that post, the exact edited body, an event timestamp later than the posting timestamp, retention of the original posting date, and retrieval of the new cancellation text through the production search module. This demonstrates a live edit update rather than a newly inserted replacement post. The user performed posting/editing and observed bot replies; the agent performed the DB verification. No claim of deletion tracking or arbitrary history access is made.

## Live pagination verification

The user published five additional matching demo posts, searched `/search python async`, and supplied the bot's first page, Next page and Previous response. Observed identity order: first page `[9,7,6,5,8]` (Results 1–5 of 6), Next `[4]` (Results 6–6 of 6), then Previous `[9,7,6,5,8]` again. The pages covered all six results without overlap; Previous restored the same order/snippets. This is a local live Telegram callback demonstration, not merely a unit-test assertion.

An agent read-only check of the stored six-result session matched that exact identity sequence and validated the production page slices, disjoint identities, complete snapshot coverage and stable return to page zero. No owner IDs, callback tokens or credentials were printed/stored in this record. The user performed the button clicks and reported their replies; the agent checked the snapshot.

## Current verification boundary

Local Docker build/start/health, 50 host/container tests, approved-post ingestion, clean live search, live edit handling and Next/Previous callbacks are now verified as described above. Credential-free replay/version/recovery tests remain distinct from the user-observed live actions; no exactly-once outbound claim is added.

Hosted HTTPS webhook registration/delivery, GitHub-hosted CI, deployment/hosting restart recovery, backup restoration and real Telegram flood-control behavior remain unverified. No public push was made during this verification sequence. This formatting repair is not retroactively counted as one of the three intentional exercises.
