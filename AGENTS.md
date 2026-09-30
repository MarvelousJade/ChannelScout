# AI-agent instructions

Build this project in a **small, understandable, interview-ready style**. Prioritize meaningful functionality, verified engineering decisions, and a development process I can follow.

## Scope and clarity

- Choose the smallest architecture that meets the requirements.
- Use clear module boundaries, descriptive names, and straightforward code.
- Add dependencies and infrastructure only when they solve a concrete problem.
- Complete one end-to-end workflow before expanding the project.
- Explain important decisions in plain language.
- Keep the project small enough that I can understand its architecture and trace its main workflows before an interview.

## Incremental development and commits

Follow this cycle:

> **Implement one meaningful increment → test → investigate failures → fix → verify → inspect the diff → commit.**

Before starting, read repository instructions, inspect Git status, preserve existing user changes, and create a short implementation checklist.

Each increment should deliver one coherent behavior. Include its relevant code, tests, and documentation in a focused commit. Do not wait until the entire project is finished to commit, and do not create arbitrary commits per file.

Define acceptance criteria before implementing each increment. Run appropriate tests and use manual smoke checks when necessary.

If a bug occurs:

- Reproduce it and investigate the root cause.
- Add a failing regression test for meaningful behavioral bugs.
- Fix mistakes within the current uncommitted increment before committing it.
- Make a separate fix commit when correcting previously committed behavior.
- Rerun affected checks before committing.

Use descriptive commit messages reflecting actual changes. For substantial changes, explain why the change was necessary and what verification passed.

Never claim verification succeeded without running it. Report blocked checks accurately. Never commit secrets or unrelated changes. Do not push or rewrite existing history unless authorized.

After each increment, briefly report the behavior added, verification result, and commit hash.

## Realistic debugging practice

Once the correct baseline works, prepare a separate learning branch with **two or three meaningful defects relevant to the project's stack**.

Choose plausible implementation mistakes that teach useful concepts, such as concurrency, state consistency, validation, authorization, caching, transactions, resource management, or failure recovery.

You may create realistic practice scenarios with:

- Simulated user reports and observable symptoms.
- Hypothetical consequences explaining why the bug matters.
- Example diagnostic hypotheses and reasoning.
- Difficult edge cases or operational constraints.

Label invented scenarios and example reasoning as practice material. Keep actual observations and measurements distinct.

For each exercise:

- Preserve a reproducible faulty checkpoint.
- Provide symptoms and reproduction steps without immediately revealing the cause.
- Prepare a meaningful regression test.
- Keep diagnosis and solutions separate from learner instructions.
- Let me investigate before revealing the solution.
- Provide progressive hints when requested.
- Verify the eventual fix and explain why it works.

Make defects resemble ordinary implementation mistakes. Avoid arbitrary crashes, obvious hints, and irrelevant broken code. Keep the main implementation branch passing.

## Engineering hurdles and evidence

Identify two or three genuine design decisions encountered during implementation. You may also propose realistic hypothetical constraints as learning exercises, clearly identifying them as such.

For each decision, record:

- The problem or constraint.
- Reasonable alternatives.
- Evidence used to compare them.
- The chosen approach and its tradeoffs.
- Remaining limitations.

Use actual tests, experiments, or measurements where useful. Report measured results honestly and distinguish local, synthetic, and production evidence.

## Documentation and interview preparation

Deliver concise documentation covering:

- What the project does and how to run it.
- Its architecture and main workflow.
- Verification commands and actual results.
- Important engineering decisions.
- Debugging exercises and separate solutions.
- Known limitations.

Prepare a 60-second introduction and a three-minute technical walkthrough.

After I complete the exercises, use my actual investigation notes to prepare concise interview stories:

> **Problem → hypothesis → evidence → decision → fix → verification.**

Include follow-up questions that test my understanding of the stack and the alternatives considered. Help me understand the work rather than memorize explanations. Base claims about my experience on what I actually investigated, changed, verified, and learned.

## Completion

Finish the agreed scope, run required checks, inspect the final diff, and commit verified agent-owned changes. Explain anything unfinished or unverified.

The result should be a working project with focused commits, reproducible evidence, and engineering decisions I can understand and discuss confidently.
