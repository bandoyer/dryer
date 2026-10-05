# A project's measure script

A project can call dryer from its own script, as bujo's `scripts/measure` does (dryer on `src`, then crapper, then mutator). The script finds dryer through `MEASURE_TOOLS`, which the helper points at this checkout.

## Sub-features

- `measure-bujo` runs bujo's `scripts/measure` in a clean clone: dryer reports `No duplicate candidates found.` and the script runs to the end.

## How to get to it (user POV)

- From the project root, run the project's script, such as `scripts/measure`.

## Driving it with verify-dryer

Preconditions:

- `$vd doctor` prints `doctor: ok`.
- `project=$($vd project ~/Work/bujo)` gives a fresh clone of bujo's committed files. `T` is the transcript path for the feature.

- **measure-bujo.** Run `$vd exec "$project" "$T" scripts/measure`. Pass: stdout starts with `No duplicate candidates found.`, stderr has no `measure: dryer found duplicate pairs` and no `Traceback`, and the exit code is `0`. A nonzero exit from crapper or mutator is bujo's own limit; record it and say which tool failed.
- **measure-dryer-only.** For the dryer step alone, run `$vd drive "$project" "$T" src`. Pass: `No duplicate candidates found.` and exit `0`.

## Gotchas

- The clone builds bujo from cold, so crapper and mutator spend minutes in `cargo`. The dryer step takes about a second.
- bujo's `mise.toml` must be trusted in the clone. The helper sets `MISE_TRUSTED_CONFIG_PATHS` for that.
- `$vd project` links `crapper` and `mutator` to the checkouts next to this repo (`../crapper`, `../mutator`). They must exist for the full script.
