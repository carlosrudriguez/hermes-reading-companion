# Validation

## Automated suite

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The release suite contains 63 standard-library tests using synthetic text and
temporary libraries. Coverage includes multilingual UTF-8 input, BOM/CRLF
preservation, nested volumes, ambiguous import plans, safe reindexing,
independent progress, fresh-process selection, aliases, exact evidence,
within-chapter cutoffs, explicit overrides, corrupt data, unsafe paths,
standalone copy installation and bounded JSON responses.

Instrumented tests check that chapter-five retrieval opens only its chapter
file and never `original.md`, and that unread chapters remain unopened.
Response tests include multibyte text and byte budgets from 1,024 to 16,000.
The copied-installation test uses a temporary working directory on either
supported operating system.

## Previous live Hermes checks

Synthetic local and hosted fresh-conversation checks exercised import,
translation, character indexing, alias lookup, persisted selection/progress
and ordinary-language inbox import without a preloaded skill.

The fixture was a 245,507-byte synthetic French novel with seven chapters and
a later revelation marker. Four hosted runs produced 39 operational JSON
responses totalling 19,061 bytes; the largest was 1,706 bytes. Trace inspection
found no later marker, spoiler override or direct source access in those runs.
These figures measure companion output, not total model context or tokens.

**Answer quality was not uniformly correct.** One hosted answer stored an
unsupported interpretation as verified. Another labelled character offsets
as line numbers. Python checks quotation location and visibility; it cannot
prove the meaning of a model's paraphrase. Successful transport is not a
claim of perfect reasoning, spoiler safety or citation rendering.

Private traces, session identifiers, deployment addresses and operational
records are deliberately excluded from the public repository. These are
historical observations, not a new live test of every supported model/version.

## Optional live testing

The installed Hermes CLI and configured inference provider are required.
These tests make model requests and may consume provider quota. They create
synthetic books in a separate library and do not send Discord messages.

```sh
# Choose a private evidence directory outside this checkout.
python3 tests/run_hermes_e2e.py --output /path/to/private/evidence --session 1
python3 tests/run_hermes_e2e.py --output /path/to/private/evidence --session 2
python3 tests/run_hermes_e2e.py --output /path/to/private/evidence --session 3
python3 tests/run_hermes_e2e.py --output /path/to/private/evidence --session 4
```

Run sessions 1, 2 and 3 in order; session 4 is independent. Use `--hermes`
if the executable is elsewhere. The harness uses a 240-second subprocess
timeout. Provider retries or timeouts are distinct from companion failures.

Inspect final answers and tool traces as well as `passed_transport`. Reports
can contain model/provider details, paths and session metadata. Keep them
private and do not attach unredacted traces to public issues.

## Limits

- No live Discord delivery or host restart/upgrade persistence test is claimed.
- The standard-library implementation supports macOS/Linux, not native Windows.
- The skill cannot sandbox other Hermes tools or erase a model's prior knowledge.
- Changed editions cannot safely reuse offsets and must use a new book ID.
- No new live inference run is implied by release unit tests passing.
