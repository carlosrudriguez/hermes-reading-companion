# Implementation and boundaries

## Components

The skill is self-contained in `skills/reading-companion`. Its `SKILL.md` is
loaded on demand through Hermes's native skill system. It invokes
`scripts/companion.py` through the existing terminal tool. The project-root
`companion.py` is only a convenience launcher for the same implementation.

The source modules each have a single responsibility:

| Module | Responsibility |
| --- | --- |
| `storage.py` | Private home, atomic JSON, locking and response envelope |
| `parsing.py` | Deterministic Markdown boundaries and structural proposals |
| `importing.py` | Byte-preserving import and conservative reindex |
| `library.py` | Library catalogue, chapter identity and saved position |
| `retrieval.py` | Bounded excerpts, literal search and source citations |
| `characters.py` | Grounded character records, aliases and fact visibility |
| `cli.py` | Argument parsing and operation dispatch |

No Python package is installed. Standard-library `fcntl` provides macOS/Linux
locking; Windows would need a small alternative locking implementation.

## Private data layout

```text
reading-companion/
  config.json              optional output-byte budget
  state.json               selected book ID
  .lock
  books/
    inbox/                 incoming Markdown files, preserved after import
    book-id/
      original.md          byte-exact UTF-8 input, never used for retrieval
      metadata.json        identity and source digest
      index.json           structural offsets, titles and per-chapter hashes
      characters.json      incrementally grounded assertions
      progress.json        chapter, exclusive character offset, status, UTC date
      chapters/
        001.md
        002.md
```

The local index can grow with the number of chapters; Hermes receives only
paged structural rows. No summaries or entire-book text are added to prompts.
Original input, line endings, BOM and frontmatter remain byte-identical.

The installer creates the inbox and prints its path. The `inbox` CLI operation
also initialises it, so a native Hermes skill installation needs no extra setup
script. It returns a paged list of filenames and sizes without opening books.
Bare import and structure-review filenames resolve in this inbox first; explicit
paths remain supported. Hermes handles these commands behind ordinary-language
requests, including in Discord on the bot's own machine/profile. No new service,
gateway extension or attachment processor is introduced.

## Parsing policy

ATX and setext Markdown headings are recognised outside fenced code blocks.
Common chapter labels in several languages and CJK conventions help select
chapter-level headings. Unknown languages still work through generic heading
levels. Plain-text chapter labels require review. Missing, mixed or single-unit
structures are reviewable. Explicit `--heading-level` selects a particular level.
Parent part/volume headings are attached to the next chapter, preserving the
entire source and its order. Printed numbering is not used as a unique key.
Unicode names and text are preserved; there is no probabilistic language guessing.
Search uses Python Unicode case-insensitive literal matching, not linguistic
stemming or accent removal. Alternative spellings may require a second query.

Parsing is intentionally conservative, not a universal Markdown parser. HTML-only
chapters, unusual numbering-only separators, complex YAML, malformed/unclosed
fences and non-UTF-8 encodings may require review or source preparation. Reindexing
never invents a mapping for changed text. Existing original, notes and progress
are retained on failure.

## Progress and character facts

Every chapter before the saved one is considered read. The current chapter is
visible through its exclusive offset. Later chapters are not even opened during
ordinary retrieval. Rewinding naturally re-hides later facts and aliases.

The model identifies characters incrementally from returned passages. A new
character requires a quote containing its name. Aliases and facts each retain
their own evidence chapter and character offsets. Relationships reference another
known character ID. Their visibility begins no earlier than either the evidence
or the target's first appearance. Assertions are marked `verified` or
`interpretation`; exact-quote checking does not establish semantic truth.
Later developments are separate facts, preserving earlier knowledge.

All character operations page their results. A character can have arbitrary
numbers of facts without returning its entire record to Hermes. If a byte budget
truncates any response, Hermes must retry with a smaller page before drawing
conclusions. Names and aliases only resolve when they are already available at
the saved position, including when querying by internal ID.

## Response accounting

The final serialized response is measured in UTF-8 bytes, including JSON and
the terminating newline. The default is 6,000 bytes; valid configured/CLI budgets
range from 1,024 to 16,000 bytes. Passage length is separately capped. Search
excerpts are bounded and a tiny one-unit book is not emitted whole by one call.
Large results drop rows or reduce a passage and advertise truncation. Source
citations use chapter-local Unicode offsets and line numbers, not invented
printed page numbers. Responses expose actual byte metrics; model-specific token
counts are deliberately not guessed.

These controls govern tool output, not the configured model's knowledge or other
Hermes tools. Restricting the agent at the OS/tool-permission layer would be a
separate architecture requiring the instance owner's approval.
