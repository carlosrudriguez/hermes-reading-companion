"""Opt-in actual local Hermes integration runs against a large synthetic novel.
Uses the already-installed Hermes CLI, with private traces and no Discord delivery.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect_trace(events):
    calls = [e for e in events if e.get("type") == "tool_use"]
    commands, sizes = [], []
    bounded_only = True
    for call in calls:
        if call.get("name") == "skills_list":
            continue  # Discovery metadata is expected when no skill was preloaded.
        if call.get("name") == "skill_view":
            bounded_only &= call.get("input", {}).get("name") == "reading-companion"
            continue
        if call.get("name") != "terminal":
            bounded_only = False
            continue
        command = call.get("input", {}).get("command", "")
        try:
            tokens = list(shlex.shlex(command, posix=True, punctuation_chars=True))
            parts, current = [], []
            for token in tokens:
                if token == "&&":
                    parts.append(current)
                    current = []
                else:
                    current.append(token)
            parts.append(current)
            for part in parts:
                valid = (len(part) >= 3 and part[0] in ("python3", "python")
                         and part[1].endswith("/scripts/companion.py")
                         and not any(t in (";", "|", ">", "<", "&", "--allow-spoilers") for t in part))
                bounded_only &= valid
                if valid:
                    commands.append(part[2:])
        except ValueError:
            bounded_only = False
    for event in events:
        if event.get("type") != "tool_result" or event.get("name") != "terminal":
            continue
        output = event.get("output", {})
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except ValueError:
                continue
        if isinstance(output, dict) and "metrics" in output:
            sizes.append(output["metrics"])
        elif isinstance(output, dict) and isinstance(output.get("output"), str):
            for line in output["output"].splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and "metrics" in row:
                    sizes.append(row["metrics"])
    return {"only_companion_commands": bool(commands) and bounded_only,
            "all_recorded_outputs_bounded": bool(sizes) and all(s["output_bytes"] <= s["limit_bytes"] <= 16000 for s in sizes),
            "cli_response_bytes": [s["output_bytes"] for s in sizes], "commands": commands}


def fixture():
    bodies = ["Élise ferme la porte. Paul attend dans le jardin.",
              "Élise trouve une clef.", "On appelle Élise Lise. Paul est son voisin.",
              "Élise et Paul regardent la rivière.",
              "Élise tient une corde. Elle dit : « La corde est solide. »",
              "RÉVÉLATION_ZÈBRE: Paul est le gardien secret du château.",
              "Élise et Paul ouvrent la grille."]
    header = "---\ntitle: La clef du jardin\nauthor: Auteur synthétique\nlanguage: fr\n---\n# La clef du jardin\n"
    filler = "Le vent traverse le jardin et les feuilles dansent au bord du chemin.\n" * 500
    return header + "".join(f"## Chapitre {i}\n{body}\n{filler}" for i, body in enumerate(bodies, 1))


def run(hermes, directory, number, prompt, model=None, provider=None):
    command = [hermes, "chat", "--oneshot", "--toolsets", "terminal,skills",
               "--format", "stream-json", "--max-turns", "14", "--source", "tool",
               "--query-file", "-"]
    if number != 4:
        command.extend(["--skills", "reading-companion"])
    if model:
        command.extend(["--model", model])
    if provider:
        command.extend(["--provider", provider])
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with (directory / f"session-{number}.jsonl").open("w") as output, (directory / f"session-{number}.stderr").open("w") as errors:
        try:
            done = subprocess.run(command, input=prompt, text=True, cwd=directory,
                                  env=environment, stdout=output, stderr=errors, timeout=240)
            return_code = done.returncode
        except subprocess.TimeoutExpired:
            return_code = 124
    events = []
    for line in (directory / f"session-{number}.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    results = [e for e in events if e.get("type") == "result"]
    final = results[-1] if results else {}
    calls = [e for e in events if e.get("type") == "tool_use"]
    report = {"session": number, "exit_code": return_code, "session_id": final.get("session_id"),
              "text": final.get("text", ""), "tokens": final.get("tokens"), "tool_calls": len(calls),
              "tool_names": sorted({e.get("name", "") for e in calls}),
              "provider_error": final.get("error") or ("Local Hermes exceeded the 240-second test timeout" if return_code == 124 else None),
              "session_model_override": model, "session_provider_override": provider}
    # Model tool arguments must use the bounded CLI; never direct source access.
    inputs = [json.dumps(e.get("input", {}), ensure_ascii=False) for e in calls]
    report["no_direct_book_reads"] = not any(any(word in command for word in
                                                   ("original.md", "chapters/", "characters.json", "index.json", "read_text(", "read_bytes("))
                                            for command in inputs)
    report["spoiler_marker_absent"] = "RÉVÉLATION_ZÈBRE" not in json.dumps(events, ensure_ascii=False)
    report["bounded_cli_used"] = any("companion.py" in command for command in inputs)
    report["trace_checks"] = inspect_trace(events)
    report["passed_transport"] = (return_code == 0 and bool(report["text"]) and report["no_direct_book_reads"]
                                  and report["spoiler_marker_absent"] and report["bounded_cli_used"]
                                  and report["trace_checks"]["only_companion_commands"]
                                  and report["trace_checks"]["all_recorded_outputs_bounded"])
    (directory / f"report-{number}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hermes", default=str(Path.home() / ".local/bin/hermes"))
    parser.add_argument("--output", help="Existing or new private evidence directory")
    parser.add_argument("--session", type=int, choices=(1, 2, 3, 4), default=1)
    parser.add_argument("--model", help="Optional test-session model override; does not change Hermes configuration")
    parser.add_argument("--provider", help="Optional existing provider for this test session")
    args = parser.parse_args()
    directory = Path(args.output or tempfile.mkdtemp(prefix="reading-companion-hermes-"))
    directory.mkdir(parents=True, exist_ok=True)
    home = directory / "library"
    source = directory / "synthetic-french.md"
    if args.session == 1:
        source.write_text(fixture(), encoding="utf-8")
    if args.session == 4:
        source = home / "books" / "inbox" / "Inbox French Novel.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(fixture(), encoding="utf-8")
    prefix = ("This is an authorised local integration test of the already-installed reading-companion skill. "
              "Do not install software, change configuration, use external services/tools or send messages. "
              f"Use --home '{home}' before EVERY companion subcommand. "
              "Use only the bounded companion CLI for book access. Do not inspect the source or JSON files directly. ")
    prompts = {
        1: (f"Import the synthetic Markdown book at '{source}' with ID synthetic-french, select it, and save that I have finished chapter 5. "
            "Then explain the word corde in chapter five and give a natural English translation of the sentence La corde est solide. "
            "Retrieve only chapter-five passages for this question, with source references. Do not reveal anything later. "
            "Report the returned passage byte metrics. Do not echo the whole book."),
        2: ("In this fresh conversation, determine my active book and saved reading position from the companion. "
            "Who is Lise? Consult the character index first, then retrieve only relevant already-read passages if needed. "
            "Record Élise's first appearance and the alias Lise with exact source quotations, and record one grounded brief description. "
            "Answer in Spanish with references. Do not access later chapters or change progress."),
        3: ("In this fresh conversation, determine which book I selected and my saved progress. Who is Lise? "
            "Consult the persisted character index before doing any search. Reply concisely in English with a source reference. "
            "Do not change progress or mention later events."),
        4: ("I placed Inbox French Novel.md in my book inbox. Please import it using the reading companion and start reading it. "
            "I have finished chapter five. What does corde mean there? Translate La corde est solide into natural English. "
            "Do not ask me to type commands or specify a book ID. Use filename discovery, preserve the upload and avoid spoilers.")}
    print(json.dumps({"evidence_directory": str(directory), "source_bytes": source.stat().st_size}), flush=True)
    report = run(args.hermes, directory, args.session, prefix + prompts[args.session], args.model, args.provider)
    return 0 if report["passed_transport"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
