# Number options

`--threshold`, `--min-lines`, and `--min-nodes` take a number. A value dryer can't use is a usage error: exit `1`, the message and the help on stderr, nothing on stdout, and no `.metrics/dry.edn` written.

## Sub-features

- `threshold-range` `--threshold` takes a number from 0 to 1, both ends included. Anything else is rejected with `--threshold requires a number from 0 to 1`: text, `nan`, `inf`, a decimal too large for a float such as `1e309`, and any finite number above 1.
- `count-options` `--min-lines` and `--min-nodes` take a non-negative integer, with no upper bound. Anything else is rejected with `<option> requires an integer`.

## How to get to it (user POV)

- Run `./dryer --threshold <n>`, `./dryer --min-lines <n>`, or `./dryer --min-nodes <n>` from a project root. `./dryer --help` lists each option and its range.

## Driving it with verify-dryer

Preconditions:

- `$vd doctor` prints `doctor: ok`.
- `project=$($vd project fixture)`. `T` is the transcript path for the feature.

- **threshold-range.** For each of `nan`, `inf`, `+inf`, `1e309`, `1.79769313486231580794e308`, `1.5`, and `1.0000000000000002`, run `$vd drive "$project" "$T" --threshold <v>`. Pass, for each: exit `1`, stderr starts with `--threshold requires a number from 0 to 1` followed by the help, stdout is empty, and the transcript shows no `.metrics/dry.edn`. Then run `$vd drive "$project" "$T" --threshold 1` and `$vd drive "$project" "$T" --threshold 0`. Pass: exit `0`; `1` reports the fixture's two `DUPLICATE score=1.00` pairs, and `0` reports at least those two.
- **count-options.** For each of `--min-lines` and `--min-nodes`, and each of `nan`, `inf`, `1e309`, and `abc`, run `$vd drive "$project" "$T" <option> <v>`. Pass, for each: exit `1`, stderr starts with `<option> requires an integer`, stdout is empty, and no `.metrics/dry.edn`. Then run `$vd drive "$project" "$T" --min-lines 0 --min-nodes 0`. Pass: exit `0` with the two pairs.
- **help.** Run `$vd drive "$project" "$T" --help`. Pass: exit `0`, and stdout has `--threshold N` with `from 0 to 1, default 0.82`.

## Gotchas

- A similarity score is never above 1, so a threshold above 1 would hide every pair. NaN would show every pair, because no score is below NaN. Both are rejected (#22).
- `float()` reads `1e309` and `1.79769313486231580794e308` as infinity. `1.0000000000000001` rounds to exactly `1.0`, so it is accepted.
- A negative value such as `--threshold -0.5` is rejected too, but with `--threshold requires a value`: dryer reads a value that starts with `-` as the next option.
- The helper gives every scratch project a folder under `TMPDIR`. Run a recipe's `project`, `drive`, and `cleanup` calls in one sandboxed command, because each sandboxed command gets its own `TMPDIR`.
