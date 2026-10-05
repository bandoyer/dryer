# Score a pair of functions

dryer scores two functions by the structure left after normalization. Call and method names, operators, and tree shape stay; local names, field names, and literal values drop out. A user sees this as the `score` dryer reports for a pair.

## Sub-features

- `score-renamed` two functions that differ only in local names, field names, or literal text score `1.0`.
- `score-callee` a different called function, method, or macro name scores below `1.0`.
- `score-operator` a different operator scores below `1.0`, including keyword operators (`in`, `is`, `not in`, `instanceof`, `typeof`) and compound assignments.
- `score-embedded` a different call inside a template string, f-string, or Rust macro argument scores below `1.0`.

## How to get to it (user POV)

- Run `./dryer --edn --threshold 0 --min-lines 1 --min-nodes 1 <file>` on a file that holds the two functions, and read `:score`.

## Driving it with verify-dryer

Preconditions:

- `$vd doctor` prints `doctor: ok`.
- `project=$($vd project empty)`. `T` is the transcript path for the feature.

Put both functions in one file, each on its own lines, then score it:

```bash
$vd put "$project" pair.rs <<'EOF2'
fn f(x: T, y: T) {
    format!("{}", approve(x))
}
fn g(x: T, y: T) {
    format!("{}", reject(x))
}
EOF2
$vd drive "$project" "$T" --edn --threshold 0 --min-lines 1 --min-nodes 1 pair.rs
```

- **score-renamed.** Change only local names or literal text between the two bodies, such as `format!("left {}", approve(x))` and `format!("right {:?}", approve(y))`. Pass: `:score 1.0`.
- **score-callee.** Change only the called name, such as `approve(x)` and `reject(x)`, or `println!` and `panic!`. Pass: `:score` below `1.0`.
- **score-operator.** Change only the operator, such as `x..y` and `x..=y` in Rust, `x not in y` and `x is not y` in Python, `typeof x` and `void x` in TypeScript, or `x &^ y` and `x | y` in Go. Pass: `:score` below `1.0`.
- **score-embedded.** Change only a call inside a TypeScript template (`` `${approve(x)}` `` and `` `${reject(x)}` ``), a Python f-string, or a Rust macro argument. Pass: `:score` below `1.0`.

## Gotchas

- With `--threshold 0` every pair is printed, so `:score` is always there to read. At the default `0.82` a low pair is simply missing.
- Use `.py`, `.ts`, `.rs`, or `.go` so dryer picks the language. TypeScript bodies need `function f(x, y) { ... }`, Python bodies need `def f(x, y):` with the body indented.
- The transcript shows each `:score` twice: once in stdout and once in the `.metrics/dry.edn` content. Read the stdout one.
- A score below `1.0` can still be high: one changed token among many shared ones. Compare against `1.0`, not against a guess.
