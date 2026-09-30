# Exercise provenance and evidence

Exercises are agent-created practice defects. Learner investigation and eventual repairs have not occurred. Correct baseline currently passes all three exercise regressions as part of 29 passing tests.

Faulty checkpoint creation/reproduction is pending. This file will record exact commits, commands and observed failures after they run. Diagnoses/solutions will not be included in this learner-facing record.

A missing-unique-tie-breaker SQL experiment performed 20 serial reads and produced only one distinct sequence. Therefore no reproduced claim of unstable ordering is made for that experiment; C uses a different realistic snapshot page-boundary defect.
