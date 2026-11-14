# Hermes Reading Companion

**Read at your own pace. Discuss what you have read, in the language you choose.**

[![Tests](https://github.com/carlosrudriguez/hermes-reading-companion/actions/workflows/tests.yml/badge.svg)](https://github.com/carlosrudriguez/hermes-reading-companion/actions/workflows/tests.yml)
[![Latest release](https://img.shields.io/github/v/release/carlosrudriguez/hermes-reading-companion)](https://github.com/carlosrudriguez/hermes-reading-companion/releases/latest)
[![MIT licence](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

A self-contained skill for [Hermes Agent](https://github.com/NousResearch/hermes-agent)
that imports Markdown books, remembers your reading position and retrieves small,
source-linked passages for discussion. Ask about a character, translate a sentence
or unpack a difficult paragraph without loading the whole novel into model context.

Indexing and search use Python's standard library. No embeddings, vector database,
background service or extra Python package is required. Your existing Hermes
model handles explanations and translation from the retrieved excerpts.

## What you can do

- **Keep your place:** separate progress for each book, saved across conversations.
- **Read across languages:** preserve the original and discuss it in your preferred language.
- **Look up characters:** incremental notes and aliases backed by exact quotations.
- **Control retrieval:** chapter-based search and passages bounded by your saved position.
- **Use ordinary messages:** local chat, hosted Hermes or your existing Discord bot.
- **Keep the library separate:** books and reading state stay outside the skill checkout.

Spoiler filtering applies to the companion's commands. A model can still make
mistakes or draw on prior knowledge. See [boundaries](#boundaries-and-privacy).

## Quick start

Requires an existing Hermes Agent installation, Python **3.10+**, and **macOS or
Linux**. Native Windows is not supported. Hermes needs terminal tool access.

```sh
git clone https://github.com/carlosrudriguez/hermes-reading-companion.git
cd hermes-reading-companion
git checkout v1.0.0
python3 install.py --copy
```

Alternatively, download and extract the source archive from the
[latest release](https://github.com/carlosrudriguez/hermes-reading-companion/releases/latest),
open a terminal in its extracted directory and run `python3 install.py --copy`.
There is no package-installation step for the companion.

The installer prints two paths:

| Location | Default |
| --- | --- |
| Installed skill | `~/.hermes/skills/reading-companion` |
| Private book inbox | `~/.hermes/reading-companion/books/inbox` |

It honours `HERMES_HOME` and an existing `READING_COMPANION_HOME`, preserves
configuration and refuses to overwrite an existing skill. For another existing
profile, add `--hermes-home /path/to/profile`. Install on the machine actually
running Hermes, including when your chat interface is elsewhere.

1. Put a UTF-8 `.md` or `.markdown` book in the printed inbox.
2. Tell Hermes: **“Import My book.md from my reading-companion inbox.”**
3. Tell it where you are: **“I have finished chapter five.”**
4. Ask: **“Explain the conversation at the bridge, using only what I have read.”**

Hermes chooses a book ID and runs the CLI for you. Ambiguous chapter splits
require your review; originals and inbox uploads are preserved. If skill discovery
needs a nudge, say “use the reading companion” or load `/reading-companion`.
If you installed through native Hermes skill tooling, ask Hermes to set up the
reading companion and show the inbox; the bundled `inbox` command creates it.

## Convert a book to Markdown

Conversion is a separate preparation step. These optional tools are **not**
companion dependencies and the installer does not install or invoke them.
Choose a tool appropriate to your file and follow its official installation guide.
Use books you are entitled to process; this skill does not remove DRM.

### PDF, Word or HTML: Microsoft MarkItDown

[MarkItDown](https://github.com/microsoft/markitdown) converts PDF and office
formats to Markdown. Once installed separately:

```sh
markitdown "My book.pdf" -o "My book.md"
markitdown "My book.docx" -o "My book.md"
```

Review chapter headings and reading order after conversion. Scanned PDFs need
OCR preparation; multi-column layouts, headers and page numbers often need
cleanup. Check the converter's processing and privacy options before using
external OCR or model services with private material.

### EPUB: Pandoc

[Pandoc](https://pandoc.org/MANUAL.html) supports EPUB input and Markdown output.
Once installed separately, convert a DRM-free EPUB:

```sh
pandoc "My book.epub" --from=epub --to=markdown --wrap=none -o "My book.md"
```

### Check the result

Save as UTF-8 and use consistent Markdown chapter headings. For example:

```markdown
# My book

## Chapter 1
The opening passage...

## Chapter 2
The next passage...
```

Keep the full text in reading order. Check for missing paragraphs, duplicate
contents pages and OCR errors before import. Copy the reviewed file into your
private inbox, then ask Hermes to import it. If splitting needs review, Hermes
shows the proposed structure before accepting it. Once you have started reading,
import an edited edition under a new ID so saved offsets remain valid.

## Read naturally

> “Start reading the book I just imported.”
>
> “I am starting chapter six.”
>
> “Who is Lise, based only on what I have read?”
>
> “Translate that passage into natural Spanish and keep the French alongside it.”
>
> “Explain the grammar in the last sentence.”
>
> “I am halfway through chapter ten.”

Starting a chapter exposes none of its text. Finishing it exposes the whole
chapter. Halfway means half its characters, including the heading, rather than
half its printed pages. Ask for an exact character offset if you need one.
Internal chapter numbers run sequentially across all parts and volumes; clarify
ambiguous printed labels before changing progress.

## Discord and hosted Hermes

Install into the **profile hosting the bot**, with terminal access to the same
private library. A local installation does not install itself on a remote host.
Upload Markdown to that host's filesystem inbox, then send an ordinary message
in a private DM or mention the bot according to its existing channel settings.

**Avoid attaching the whole novel directly to a Discord message.** Hermes's
attachment handling can insert text into context before a skill runs. Filesystem
upload followed by a plain message is the intended bounded-retrieval workflow.
See the [official Discord guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord).

Use a dedicated private profile/library for one reader. Reading state is per
library, **not per Discord user**. There is no automatic cross-machine sync.
The installer does not restart gateways or change bot configuration.
See [hosted installation and migration](docs/MIGRATION.md) for setup, transfer,
updates and rollback.

## Optional CLI

Hermes normally runs these commands for you. From the source checkout:

```sh
python3 companion.py inbox
python3 companion.py import "My book.md"
python3 companion.py list
python3 companion.py select my-book
python3 companion.py progress --chapter 5 --finished
python3 companion.py inspect
python3 companion.py search "bridge" --chapter 5
python3 companion.py passage --chapter 5 --start 100 --length 800
python3 companion.py characters "Lise"
```

Run `python3 companion.py --help` or append `--help` to a subcommand for options.
In a copied installation, use `scripts/companion.py` inside the installed skill.

Private state defaults to `${HERMES_HOME:-~/.hermes}/reading-companion`.
`READING_COMPANION_HOME` or global `--home PATH` chooses another library.
Global flags go **before** the subcommand; for example:

```sh
python3 companion.py --home /path/to/private/library --max-bytes 3000 list
```

Optional `config.json` in that private home follows [config.example.json](config.example.json).
`--book ID` targets a book without changing selection. An ambiguous import returns
`review_required` and a plan ID; page through `inspect-plan "My book.md"` and repeat
`import` with `--accept-plan PLAN_ID` and the same metadata/heading options.

## Boundaries and privacy

- Book retrieval reads chapter files, never the saved `original.md`.
- Operational JSON defaults to **6,000 UTF-8 bytes**, including its envelope and
  newline, with a **16,000-byte absolute ceiling**. CLI help is plain text.
- Passage requests default to 1,200 characters and cap at 2,400. Search is literal,
  Unicode case-insensitive matching, without embeddings or semantic search.
- Saved progress gates text, future headings, aliases and character facts.
  Explicit `--allow-spoilers` applies to one operation and never advances progress.
- Character notes require exact already-read quotation evidence. This validates
  location and visibility, **not the truth of the model's interpretation**.
- Books and state remain in the private filesystem, but retrieved excerpts go to
  your configured model provider. Hermes may retain conversations/tool traces
  according to its settings. This is not a promise of fully offline discussion.
- Byte limits govern companion responses, not Hermes prompts, tools, history,
  model tokens or final answers. The skill does not sandbox Hermes's other tools
  or remove a model's prior knowledge of a novel.
- Reindexing refuses incompatible source/boundary changes. Atomic JSON writes
  and a library lock protect ordinary updates; retain backups for recovery.

No personal books, credentials, live configuration or operational traces are
shipped. When reporting a problem, use synthetic examples and redact paths,
account details, session IDs and any private book excerpts.

## Development and testing

```sh
# Development symlink: source edits are visible to Hermes immediately.
python3 install.py

# Offline suite with synthetic fixtures and temporary libraries.
python3 -m unittest discover -s tests -v
```

Do not run `--copy` over a development symlink. The installer intentionally
refuses to overwrite existing destinations. Back up and move an existing copied
skill outside skill discovery before installing an update; keep the library.

The GitHub workflow tests Python 3.10 and 3.14 on Linux and macOS. Optional live
Hermes tests consume your configured provider's quota and must be reviewed for
answer quality as well as transport. See [validation and known limitations](docs/VALIDATION.md),
[architecture](docs/ARCHITECTURE.md) and the [changelog](CHANGELOG.md).

Contributions are welcome through issues and pull requests. Keep changes focused,
include relevant tests and use synthetic fixtures. Do not include books, credentials,
private reading state or unredacted model traces.

## Licence

[MIT](LICENSE). The software licence does not grant rights to third-party books.
This is an independent community skill, not an official Nous Research product.
