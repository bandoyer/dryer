# Changed files

`./dryer --changed` compares only the source files git reports as added or modified, with one another. It does not compare them against unchanged files.

## Sub-features

- `changed-only` an edited file and a new file are compared; untouched files are not.
- `changed-none` with nothing changed, dryer says there is nothing to analyze and replaces `.metrics/dry.edn` with an empty report.

## How to get to it (user POV)

- Run `./dryer --changed` from a git project root.

## Driving it with verify-dryer

Preconditions:

- `$vd doctor` prints `doctor: ok`.
- `project=$($vd project fixture)`. `T` is the transcript path for the feature.

- **changed-none.** Run `$vd drive "$project" "$T" --changed`. Pass: exit `0`, stdout is `No source files to analyze.`, and the transcript shows `.metrics/dry.edn` written as `{:candidates []}`. Every successful run replaces the report, even one that compares no files.
- **changed-only.** Add a copy of the invoice function under a new name: `$vd put "$project" src/billing/credit.py` with `def credit(note):` and the same body shape as `src/billing/invoice.py`, then `git -C "$project" add -A`. Run `$vd drive "$project" "$T" --changed`. Pass: no pair names `invoice.py` or `receipt.py`, because they did not change; the new file alone has nothing to pair with, so stdout is `No duplicate candidates found.` Then edit `src/billing/receipt.py` (add a comment line) and drive again. Pass: `DUPLICATE score=1.00` for `src/billing/credit.py:1-4` with `src/billing/receipt.py:1-4`.

## Gotchas

- `--changed` reads `git status`; an untracked file counts only once git sees it (`git add`).
- A run outside a git repository fails. The fixture and `empty` projects are git repos.
