# Roadmap

Version 1 covers intake with diagnostics, an editable outline, just-in-time sections and highlight-and-ask. The next phases build on data v1 already stores: exercise blocks keep their hints and full solutions, and every margin thread records the block it belongs to plus the exact quote and the text around it.

## Phase 2: adaptive exercises, hints and grading

Today exercises reveal hints one at a time and show the stored solution on request.

- **Grading.** Learners submit an answer (`POST /api/sections/{id}/exercises/{block_id}/attempts`). A grader call with a structured output (`verdict`, `feedback`, `misconception`, `suggested_hint`) compares it with the stored solution and, for open questions, a rubric written alongside the exercise. Code exercises run against tests in a sandbox (for example Claude's code execution tool) instead of relying on the model's judgement alone. Solutions stop being sent to the browser until the learner gives up or succeeds.
- **Attempts.** A new `exercise_attempt` table records the answer, verdict, feedback and hints used.
- **Adapting.** Per-concept mastery estimates on the learner profile (a simple knowledge-tracing or Elo-style update per attempt) drive what happens next: another exercise on the same concept at the right difficulty, a short remediation block, or compressing material the learner has mastered in later sections, which get the mastery summary in their prompts.

## Phase 3: folding good answers back into the course

- A **"This helped"** button on tutor replies, stored on the message.
- **"Add to the lesson"** inserts a new `clarification` block after the block the thread is anchored to, in the learner's copy, styled distinctly and linked to its thread.
- For courses shared between learners, the model merges the helpful answers about one passage into a single clarification and proposes it as a revision. Section content becomes versioned (`section_revision`) so a revision can be reviewed, accepted and rolled back.

## Phase 4: flagging passages many learners question

This needs courses that many learners read, so it follows shared courses and accounts.

- Group threads by section, block and overlapping quote (the stored anchors make overlap cheap to compute) into a per-passage confusion score.
- Show a heatmap to course maintainers, and flag passages above a threshold for rewriting. The rewrite prompt includes the most common questions so the new text answers them up front.
- Measure whether a rewrite worked by comparing question rates before and after. Aggregate counts only, with an opt-out.

## Other next steps

- **Accounts and multi-user:** Supabase Auth (JWT verification in FastAPI), a `user_id` on courses and threads, and shared course templates with per-learner progress.
- **Streaming:** stream tutor replies token by token over Server-Sent Events, and stream a section's text within a block (blocks already stream one by one).
- **Outline edits after starting**, for sections that haven't been written yet.
- **Bring your own sources:** ground research in uploaded PDFs or notes, as textbook_quality's local-document mode did.
- **Usage and cost tracking** per course from the API's usage data, with optional limits.
- **An eval set** for section quality and tutor answers (accuracy, level, adherence to the learning style) to tune prompts, models and effort levels.
- **Diagram repair:** when a Mermaid diagram fails to parse in the browser, ask the model to fix it and store the corrected version.
- **A durable job queue** (for example Postgres-backed) for running many API processes; today jobs run in-process and stale ones are reclaimed after a restart.
- **Front-end polish:** code-split the reader for a faster first load, an accessibility audit, and translations.
