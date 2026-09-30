# Exercise provenance and regression evidence

Agent-created practice defects, not production incidents or learner discoveries. Learner investigation/repair has not happened. Solutions/hints are isolated on an instructor branch and are not included in these instructions.

## Checkpoints

| Reference | Commit | Targeted actual observation |
|---|---|---|
| baseline-verified | a6edf40 | 29 tests passed, including all three exercise regressions |
| exercise-a | 24b3902 | Concurrent receipt/post counts `(2, 2)` instead of `(1, 1)`; 1 failed |
| exercise-b | 824e67a | Stored `Outdated coroutine examples` instead of `Corrected coroutine examples`; 1 failed |
| exercise-c | 594eb77 | First three pages had 15 entries but 13 unique identities; 1 failed |

Learning branch `codex/channelscout-learning` contains all three sequential faulty checkpoints. Later checkpoints retain earlier defects. Baseline branch is `codex/channelscout`; it does not include the learning-only migration. Instructor branch contains notes only and does not silently repair the learner's checkpoints.

## Commands actually run

All used the isolated local `scout_learning` database on loopback 55432, not the baseline `scout_test` DB. PTB_TIMEDELTA=1 was set. These are real PostgreSQL test failures, not mocked duplicate state or artificial application crashes.

```sh
TEST_DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_learning pytest tests/test_exercises.py::test_exercise_a_concurrent_delivery -q
TEST_DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_learning pytest tests/test_exercises.py::test_exercise_b_delayed_event -q
TEST_DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_learning pytest tests/test_exercises.py::test_exercise_c_page_boundaries -q
# At exercise-c:
TEST_DATABASE_URL=postgresql://nobody@127.0.0.1:55432/scout_learning pytest tests/test_exercises.py -q
```

Observed combined result at exercise-c: **3 failed in 7.26s**, one intended assertion failure per exercise. No unrelated exception was used as reproduction evidence. Individual observed times: A 6.68s, B 5.90s, C 9.91s (fixture/runtime overhead included, not a performance benchmark).

A's test schedules overlapping reads to reliably reproduce concurrent behavior; production code contains no injected sleep/barrier/crash. C's data asserts tied scores/dates before checking boundaries. A missing-unique-tie-breaker SQL experiment performed 20 serial reads and produced only one distinct sequence; it did not visibly reproduce instability, so no claim to the contrary is made.

After switching back to baseline and the separate baseline database, the final suite passed **31 tests**, including these three regressions and a concurrent-newer-edits convergence check. Additional real validation-redaction regression passed after its separate fix; it is not counted as an invented learning defect.

Eventual learner fixes remain pending. A passing baseline is evidence of the intended design, not evidence that the learner repaired a faulty checkpoint or that a repair migration was implemented.
