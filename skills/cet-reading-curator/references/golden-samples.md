# Eight reviewed baselines

The six careful-reading baselines live in the project seed `seed/reading_catalog.py` and are inserted idempotently:

| Difficulty | Topic | Title |
|---:|---|---|
| 1 | 健康 | Small Health Choices That Last |
| 2 | 教育 | Using AI in Class with Clear Boundaries |
| 3 | 文化 | Why Free Museums Still Need Good Design |
| 4 | 环境 | Wetlands as Working Urban Infrastructure |
| 5 | 社会 | Digital Services Are Useful Only When People Can Reach Them |
| 6 | 科技 | When Robots Leave Controlled Spaces |

Each has five hand-written items, Chinese explanations, exact evidence spans, source metadata, and an explicit original-adaptation note.

The banked-cloze and long-matching baselines are in `assets/non-careful-golden-samples.json`. They demonstrate output structure and validation; they are not part of the 180-passage careful-reading inventory.
