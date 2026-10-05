# Find duplicates

A user runs `./dryer` in a project, with or without paths, and reads the pairs of functions whose structure is close enough to review, closest first. Each run also writes `.metrics/dry.edn` with the same pairs.

## Sub-features

- `find-text` prints `DUPLICATE score=<n>` blocks, each naming both spans as `file:start-end`.
- `find-edn` prints the same pairs as EDN with `--edn`.
- `find-paths` limits the run to the named files or folders, or to files whose path contains a filter text.
- `find-skip-tests` leaves out `tests/` and `test_*.py` unless named.
- `find-metrics` writes `.metrics/dry.edn` on every successful run, replacing the last one.

## How to get to it (user POV)

- Run `./dryer` from a project root, or `./dryer <path-or-filter> ...`.

## Driving it with verify-dryer

Preconditions:

- `$vd doctor` prints `doctor: ok`.
- `project=$($vd project fixture)`. `T` is the transcript path for the feature.

- **find-text.** Run `$vd drive "$project" "$T"`. Pass: exit `0`; stdout has two `DUPLICATE score=1.00` blocks, one for `src/billing/invoice.py:1-4` with `src/billing/receipt.py:1-4`, one for `src/tally/lib.rs:1-5` with `src/tally/lib.rs:7-11`; nothing names `src/greet.go` or `tests/`.
- **find-edn.** Run `$vd drive "$project" "$T" --edn`. Pass: stdout is `{:candidates [...]}` with the same two pairs, each with `:language`, `:left`, `:right`, and node counts.
- **find-paths.** Run `$vd drive "$project" "$T" src/billing`, then `$vd drive "$project" "$T" tally`. Pass: the first reports only the Python pair, the second only the Rust pair.
- **find-skip-tests.** Run `$vd drive "$project" "$T" src/billing tests/test_invoice.py`. Pass: the named test file now pairs with the invoice and receipt functions.
- **find-metrics.** In any drive above, the transcript's `.metrics/dry.edn` line shows a new hash and the file's content matches the pairs reported. Tracked files changed: `(none)`.

## Gotchas

- `Wrote <path>/.metrics/dry.edn` goes to stderr, not stdout.
- `No duplicate candidates found.` on stdout is a successful run with no pairs, exit `0`.
- The fixture's functions are 4 to 5 lines. A smaller function is skipped at the default `--min-lines 4`.
