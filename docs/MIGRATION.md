# Hosted installation and migration

Install the skill on the machine and profile running Hermes. A local install
does not install it on a hosted instance or synchronise reading state.

## Check the target

Use your existing terminal or hosting dashboard to confirm:

- Python 3.10 or later is available on macOS or Linux.
- Hermes terminal execution can access the skill and private library.
- The library lives on a private writable volume with suitable persistence.
- You have a backup and know the provider's upload and restore procedures.

A directory being writable does not prove that it survives a restart or upgrade.
Check your provider's documentation and verify persistence separately.

## Install

Download a release or clone the repository on the target, then run:

```sh
python3 install.py --hermes-home /path/to/existing/hermes-profile --copy
```

The profile must already exist. The installer creates the private inbox and
prints its location. It refuses to overwrite an existing skill and does not
change models, integrations, gateway settings or schedules.

For a custom library, pass `--library-home /path/to/private/reading-companion`
and set `READING_COMPANION_HOME` to the same location in Hermes's terminal
environment. Confirm that environment variables reach actual terminal calls.
Global CLI `--home PATH` is also available for explicit operations.

## Fresh library or transfer

For a fresh library, upload UTF-8 Markdown into the printed inbox. In a hosting
Files interface, navigate to that exact folder before uploading. Ask Hermes:

> Import My book.md from my reading-companion inbox and start reading it.

For a transfer, pause reading-state writes and back up the **entire private
reading home**, including inbox, originals, chapters, metadata, indexes,
character notes, progress and `state.json`. Transfer that snapshot separately
from the source repository using your normal private file-transfer method.
Preserve access permissions and verify selection/progress from a new Hermes
conversation. Do not put the snapshot on GitHub.

There is no automatic sync or merge between independent libraries. Choose one
active instance or manage explicit transfers to avoid divergent state.

## Discord

The bot must use the same Hermes profile, terminal filesystem and private
library as the installation. Use a dedicated private profile/library for one
reader: selection and progress are per library, not per Discord user.

Upload books to the filesystem inbox, then send an ordinary message in a DM
or mention the bot according to its existing channel settings. Avoid attaching
the whole novel to Discord: host attachment processing can inject text into
model context before the skill runs. This companion does not change that
processing. See the [official Discord guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord).

## Verify and update

Check `inbox`, `list` and `inspect` through the actual Hermes terminal. Use a
synthetic book for a bounded passage and saved-progress check across two fresh
conversations. Check deployment persistence separately; Discord message delivery
is another independent check.

To update, stop companion operations, back up the private reading home, and
move the existing skill directory outside Hermes's skill discovery tree.
Install the new version with `--copy`. Confirm normal reading before removing
the previous skill backup. For a development symlink, keep the symlink and
update its source checkout instead of running the copy installer over it.

To roll back, restore the previous skill directory. Preserve private reading
data; restore a consistent full snapshot if its format requires rollback too.
Never remove the library merely to uninstall or replace the skill.
