# Debugging practice — learner instructions (no solutions)

These are deliberately introduced implementation defects, **not production incidents** or discoveries you have made. Baseline branch `codex/channelscout` must stay passing. The learning branch has sequential faulty checkpoints (`exercise-a`, `exercise-b`, `exercise-c` tags). Later checkpoints retain earlier defects; run the targeted regression for each exercise. Instructor diagnoses/hints are kept on a separate branch and should be requested only when you want them.

Use a dedicated disposable `scout_learning` PostgreSQL database. Faulty migrations change constraints; **never** use the baseline/live DB. The tests truncate app tables. Use a separate local venv or the baseline venv with the checkout's source; don't run a previously built container image and assume it contains your current checkout.

```sh
# Create once, using your local DB credentials:
createdb -U scout -h localhost scout_learning
export TEST_DATABASE_URL=postgresql://scout:scout_local_only@localhost:5432/scout_learning
# Replace <letter> with a, b or c; create your own work branch from the checkpoint:
git switch -c codex/my-exercise-<letter> exercise-<letter>
pytest tests/test_exercises.py::test_exercise_<letter>_<suffix> -q
```

On Windows use PowerShell environment syntax. Docker-only users can run `createdb` with `docker compose exec db` and rebuild the learning checkout's image with MODE=off, using only the disposable learning database. Never reuse a polling/webhook container for faulty practice.

## A — repeated delivery

**Simulated report:** “After concurrent re-delivery of a channel post, the index contains repeated records.” This report is practice material. The targeted reproduction actually checks receipt and post counts; recorded outputs are in `evidence.md`.

```sh
pytest tests/test_exercises.py::test_exercise_a_concurrent_delivery -q
```

Expected acceptance after your fix: concurrent delivery leaves one receipt and one stored post. The test controls the timing of database reads to make overlap reproducible; it does not inject crashes or exceptions into app code. Inspect rows/counts as well as the assertion output.

## B — revised content reverts

**Simulated report:** “A corrected description looked right, then an older delivery brought back the outdated wording.” No customer incident is claimed.

```sh
pytest tests/test_exercises.py::test_exercise_b_delayed_event -q
```

Expected acceptance after your fix: stored text remains `Corrected coroutine examples` after delayed delivery. Compare source timestamps, processing order and stored state. Capture your own hypothesis before requesting hints.

## C — repeated item on the next page

**Simulated report:** “One result appears at the end of a page and again at the beginning of the next page.”

```sh
pytest tests/test_exercises.py::test_exercise_c_page_boundaries -q
```

Expected acceptance after your fix: the first three pages contain exactly the first fifteen ordered identities once each. Seeded records include tied relevance scores and dates. This is a snapshot pagination exercise. An initial missing-order-tie-breaker experiment did not visibly reproduce instability, so that unproven scenario is not presented as reproduced evidence.

## Investigation notebook

Record: symptom, reproduction command/output, hypothesis, inspected code/state, unsuccessful checks, chosen change, final diff and rerun output. Identify AI hints separately from your reasoning. Ask for “exercise A/B/C hint 1”, then further hints or the solution when ready. Eventual fixes will be implemented/verified **after** you investigate, not silently applied to the learning checkpoints now.

When returning to baseline, switch `codex/channelscout` and restore TEST_DATABASE_URL to a **different** pristine test database. A faulty migration cannot be undone merely by switching Git branches. Drop/recreate only your disposable learning DB if resetting practice; obtain explicit permission before any destructive action outside that practice DB.
