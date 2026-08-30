# Website runtime contract

The project copy of `resources/reading_generation_policy.json` is the runtime-readable policy. Keep it aligned with this skill.

## Careful-reading package

Return valid JSON with `title`, `content`, and exactly five `questions`. Each question has:

```json
{
  "type": "detail",
  "question": "English stem",
  "options": ["A text", "B text", "C text", "D text"],
  "answer": "B",
  "explanation": "Chinese explanation",
  "evidence_text": "exact supporting span from the generated passage"
}
```

Validation checks word range, SHA-256 duplication, four unique options, A-D answer, Chinese explanation, exact evidence presence, allowed item type, five-item count, and eight-word source overlap.

## Inventory invariants

- Matrix: 6 topics x 6 difficulty levels x 5 unread careful-reading passages.
- Completed passages remain queryable as history and leave the default unread pool.
- A non-duplicate completion queues exactly one same-cell replacement.
- Jobs persist in SQLite and move through `pending`, `running`, `paused_config`, `paused_budget`, `failed`, or `completed`.
- A job has three total attempts. Missing API key, insufficient balance, or the shared CNY 5 monthly limit pauses work without fabricating content.
- Generated usage must be written to the site's AI ledger under `reading_library`.

Do not expose provider keys, source full text, hidden prompts, or correct answers through new inventory/status responses.
