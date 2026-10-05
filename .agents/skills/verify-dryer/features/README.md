# dryer verification map

This folder is the maintained source for verifying what a dryer user sees. Read this index before driving the CLI, then use the matching feature file as the recipe.

## Baseline preconditions

- `$vd doctor` prints `doctor: ok` for the commit under test (`vd=.agents/skills/verify-dryer/bin/verify-dryer`).
- Each recipe starts from a fresh scratch project from `$vd project`.
- No real project folder is driven. A real project is cloned first.

## Driving conventions

- Run every dryer command through `$vd drive <project> <transcript> <args...>`, and every project command through `$vd exec`. The one exception is [install-minimum](./install-minimum.md), which runs dryer from another environment through `exec`.
- Write source files into a scratch project with `$vd put <project> <path>`, content on stdin.
- Treat every command as literal. Keep quoted text unchanged.
- `--min-lines 4` and `--min-nodes 20` are the defaults. A one-line or one-expression function needs `--min-lines 1 --min-nodes 1`, or dryer skips it before comparing.
- Two functions that share a line range, such as two one-line functions on one line, are still two functions, and dryer pairs them. A text report shows both sides with the same `file:start-end`, so put each function on its own lines when you need to tell the sides apart.

## Proof and skip reporting

- CLI proof is the transcript: command, stdout, stderr, exit code, the `.metrics/dry.edn` written, and tracked files changed.
- Record the feature ID with every transcript.
- Report an unreachable path with the attempted command and the unmet precondition.

## Features

- [Find duplicates](./find-duplicates.md) covers the text and EDN reports, path and filter arguments, skipped test files, functions that share a line range, and the `.metrics/dry.edn` file.
- [Score a pair of functions](./score-pair.md) covers what normalization keeps and drops: renamed locals and literal text still match, a different callee, operator, or embedded call does not.
- [Changed files](./changed-files.md) covers `--changed`, which compares only the files git reports as added or modified.
- [Install with the lowest dependencies](./install-minimum.md) covers running dryer with every direct dependency at the lowest version `pyproject.toml` allows.
- [A project's measure script](./project-measure.md) covers a real project's own script that calls dryer, such as bujo's `scripts/measure`.
