# Install with the lowest dependencies

`pyproject.toml` declares a lowest version for each dependency, such as `tree-sitter-language-pack>=1.12.5`. A user whose environment already holds those versions must get a working dryer. The `minimum` job in `.github/workflows/ci.yml` runs the test suite this way; this recipe drives the CLI.

## Sub-features

- `install-minimum` dryer, run with every direct dependency at its declared lowest version on Python 3.11, parses and pairs functions in each tree-sitter language.

## How to get to it (user POV)

- Install the dependencies at their lowest allowed versions, then run `dryer` in a project.

## Driving it with verify-dryer

Preconditions:

- `uv` is installed. It fetches Python 3.11 if the machine lacks it, and needs network access once.
- `project=$($vd project empty)`. `T` is the transcript path for the feature.

- **install-minimum.** From the repo root, build the environment outside the checkout and record what it installed:

  ```bash
  env=$(mktemp -d)
  uv venv --python 3.11 "$env/venv"
  VIRTUAL_ENV="$env/venv" uv pip install --resolution lowest-direct -r pyproject.toml
  VIRTUAL_ENV="$env/venv" uv pip freeze | grep '^tree-sitter'
  ```

  Put one pair of functions in each language:

  ```bash
  printf 'def a(x):\n    return f(x) + 1\n\ndef b(y):\n    return f(y) + 2\n' | $vd put "$project" p.py
  printf 'fn a(x: i32) -> i32 { f(x) + 1 }\nfn b(y: i32) -> i32 { f(y) + 2 }\n' | $vd put "$project" r.rs
  printf 'package p\nfunc a(x int) int { return f(x) + 1 }\nfunc b(y int) int { return f(y) + 2 }\n' | $vd put "$project" g.go
  printf 'function a(x) { return f(x) + 1; }\nfunction b(y) { return f(y) + 2; }\n' | $vd put "$project" t.ts
  printf 'class J {\n  int a(int x) { return f(x) + 1; }\n  int b(int y) { return f(y) + 2; }\n}\n' | $vd put "$project" J.java
  $vd exec "$project" "$T" env PYTHONPATH="$PWD/src" "$env/venv/bin/python" -m dryer --edn --threshold 0 --min-lines 1 --min-nodes 1
  ```

  Pass: the freeze lists `tree-sitter==` and `tree-sitter-language-pack==` at the floors in `pyproject.toml`; the drive exits `0`, its stdout holds five pairs, one per `:language` (go, java, python, rust, typescript), and stderr has no `Traceback`. The transcript repeats the pairs under `.metrics/dry.edn`, so count stdout only. Remove `$env` afterwards.

## Gotchas

- `-r pyproject.toml` installs only the dependencies, and `PYTHONPATH` runs this checkout's `src`, so nothing is written inside the checkout.
- The language pack downloads each grammar on first parse and caches it per pack version under `~/.cache/tree-sitter-language-pack/v<version>`.
