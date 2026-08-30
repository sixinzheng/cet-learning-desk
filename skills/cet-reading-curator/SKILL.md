---
name: cet-reading-curator
description: Curate authoritative English source material and create or validate CET-4/CET-6 banked-cloze, long-matching, and careful-reading exercises for this learning site. Use when sourcing articles, adapting source facts, calibrating six difficulty levels, writing reading questions, or auditing the reading inventory. Do not use to reproduce full copyrighted articles or claim generated material is an authentic past paper.
---

# CET Reading Curator

Create traceable, original CET-style reading practice from authoritative public facts.

## Route the task

- For exam structure, difficulty, deletion/adaptation rules, and question balance, read [references/exam-spec.md](references/exam-spec.md).
- For source discovery, provenance, copyright-safe rewriting, and network boundaries, read [references/sources.md](references/sources.md).
- For website fields, inventory jobs, validation, and output contracts, read [references/runtime-contract.md](references/runtime-contract.md).
- For the eight hand-reviewed baselines, read [references/golden-samples.md](references/golden-samples.md). The two non-careful samples are in [assets/non-careful-golden-samples.json](assets/non-careful-golden-samples.json).

## Non-negotiable outcomes

1. Preserve the source URL, title, publication date, retrieval date, topic, difficulty, and adaptation note.
2. Treat the source only as factual reference. Rewrite the passage's organization and sentences; do not preserve a run of eight or more source words.
3. Label generated passages as `题材参考` and `本站原创改写`; never label them as media originals or authentic CET papers.
4. Use exactly the requested CET format. Every objective item needs one best answer, a Chinese explanation, and a precise evidence span.
5. Reject unverifiable facts, ambiguous answers, duplicate passages, missing evidence, unsupported URLs, and output that misses the level-specific length or reasoning target.
6. Keep generation idempotent and auditable. Never silently replace completed history or bypass the site's monthly AI budget.

## Working method

Discover candidates only from the maintained allowlist, record the facts needed for the exercise, then close the source. Draft an original passage from the fact brief, create items, and run deterministic validation before inserting anything. If validation fails, return the concrete reason and leave the inventory job retryable; do not weaken the rules to force acceptance.

When asked to expand the library, maintain five unread careful-reading passages for every canonical topic and difficulty. A completed passage remains in history and creates one replacement job for the same cell.
