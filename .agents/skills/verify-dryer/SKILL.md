---
name: verify-dryer
description: Drive this checkout's dryer CLI (the structural duplicate finder) against a scratch project (a built-in fixture, an empty repo you fill with `put`, or a clone of a real repo) and capture proof (command, stdout, stderr, exit code, the .metrics/dry.edn it wrote, and tracked files changed). Use to verify any dryer behaviour the way a user would see it, including how a pair of functions scores and a project's own measure script that calls dryer.
---

# Verify dryer

dryer is a command-line duplicate finder. The only surface is the `./dryer` launcher at the repo root. It reads source files, normalizes each function, prints pairs whose structural similarity clears `--threshold`, and writes `.metrics/dry.edn` in the working directory. A drive never runs against a real project folder: every drive uses a scratch project.

All commands below use the helper at `.agents/skills/verify-dryer/bin/verify-dryer`. Run it from the repo root; call it `vd` for short. Run every helper command through the sandbox your caller names (skillflow's `bin/sandbox`), because each one runs dryer's code:

```bash
vd=.agents/skills/verify-dryer/bin/verify-dryer
```

## Launch

There is no server and no build. `./dryer` creates `.venv` on first use and installs this checkout into it in editable mode, which needs network access once.

It is ready when `$vd doctor` prints `doctor: ok`. Teardown is `$vd cleanup <project>` for each scratch project you made.

## Doctor

```bash
$vd doctor
```

It reads no project and writes nothing outside `.venv`. Its `./dryer --help` call creates `.venv` if it is missing, as Launch says. It fails if the launcher is missing, `./dryer --help` fails, or `.venv` imports `dryer` from anywhere but this checkout's `src` (a copied or stale `.venv` would test other code). On success it prints the Python version, the imported path, and the checkout's commit and branch (and whether `src/`, the launcher, or `pyproject.toml` have uncommitted changes).

## Drive

```bash
project=$($vd project fixture)                 # git repo: a Python pair and a Rust pair that each score 1.0, a Go file, a skipped test file
project=$($vd project empty)                   # empty git repo; add files with put
project=$($vd project ~/Work/bujo)             # or a fresh git clone of a real project (committed files only)
$vd put "$project" src/a.rs <<'EOF'            # write one file into the project from stdin
fn f(x: T, y: T) {
    x..y
}
EOF
$vd drive "$project" <transcript> --edn --threshold 0 --min-lines 1 --min-nodes 1 src/a.rs
$vd exec "$project" <transcript> scripts/measure
```

`drive` runs this checkout's `./dryer <args...>` with the project as the working directory, exactly as a user would type it there. `exec` runs any project command the same way, such as a measure script that calls dryer. Both append one block to `<transcript>` and also print it:

- the command, the date and time, the dryer commit, and the exit code
- stdout and stderr
- `.metrics/dry.edn`: its hash before and after, and its content when the run changed it
- tracked files changed in the project (`(none)` when dryer left the source alone)

Both set `MEASURE_TOOLS` to a folder in the scratch area that links `dryer` to this checkout, and `crapper` and `mutator` to their checkouts next to it. A measure script that reads `MEASURE_TOOLS` therefore runs the dryer under test, not another copy. Both also set `MISE_TRUSTED_CONFIG_PATHS` to the project, so a cloned project's `mise.toml` works.

The features you can drive, and the end state that proves each one, are in [features/README.md](features/README.md).

## Evidence

- Put transcripts where the caller asks, for example `<run folder>/artifacts/verify/round-1/criterion-1.txt`. Never put them inside the scratch project: cleanup removes it.
- Proof is the transcript: the action (command), what the user saw (stdout, stderr, exit code), and the side effects (`.metrics/dry.edn` written, tracked files unchanged). Check all three.
- Use the real user path only: the `./dryer` launcher with real arguments, or the project's own script. Don't import `dryer` in Python, and don't treat `pytest` as proof.
- Exit codes: `0` the report was written, `1` usage error, `2` unknown `--format`. A Python traceback exits `1` too, so read stderr.

## Cleanup

```bash
$vd cleanup "$project"
```

This removes only a scratch folder that `$vd project` created (`$TMPDIR/dryer-verify.*` or `/tmp/dryer-verify.*`), given as the project or the scratch folder itself, after resolving `..` and symlinks. It refuses any other path, including a folder inside the project. `put`, `drive`, and `exec` likewise refuse a project outside a scratch folder, and `put` refuses a path that leaves the project, so a real checkout can't be written or driven by mistake. Transcripts stay where you wrote them.

## Helpers

`bin/verify-dryer` subcommands: `doctor`, `project fixture | empty | <git repo>`, `put <project> <relative path>` (content on stdin), `drive <project> <transcript> [dryer args...]`, `exec <project> <transcript> <command> [args...]`, `cleanup <project>`. Running it with no arguments prints usage.
