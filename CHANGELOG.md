# Changelog

## 1.0.0 · 14 November 2026

First public release.

- Self-contained Hermes skill using only the Python standard library.
- Deterministic UTF-8 Markdown import with review for ambiguous chapter splits.
- Private inbox, automatic book IDs and preserved source uploads.
- Per-book progress and persisted active selection across conversations.
- Bounded passage/search responses and progress-based spoiler filtering.
- Incremental character notes and aliases with exact-quotation evidence.
- Translation, vocabulary and literary discussion through your Hermes model.
- Standalone copy installation and development symlink installation.
- Generic hosted/Discord setup guidance and optional synthetic live-test harness.
- Portable copied-installation test, with no macOS-specific working directory.

### Known limitations

The model can still make unsupported interpretations or mislabel citations.
Quote validation checks location and visibility, not semantic entailment.
Reading state is per library, not per messaging user. Discord delivery and
host restart/upgrade durability have not been tested. See
[validation](docs/VALIDATION.md) for the scope of testing.
