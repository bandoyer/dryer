# Rust test code

dryer compares production code, not tests. In Rust, a test can sit next to the code it tests, so dryer reads the attributes and the crate's module tree to tell them apart. A user sees this as which functions can appear in a reported pair.

## Sub-features

- `test-code-pair` two similar `#[test]` functions are not reported at the default settings; two similar production functions beside them still are.
- `test-code-attributes` a function with `#[test]`, `#[tokio::test]`, or `#[test_case(1)]`, one in a `#[cfg(test)] mod`, and one in a file that starts `#![cfg(test)]` are not compared. One with `#[cfg(not(test))]`, `#[cfg(any(test, feature = "x"))]`, or the look-alike `#[test_cases]` is.
- `test-code-module-files` a module file the crate reaches only through test code is not compared: `#[cfg(test)] mod checks;` (`src/checks.rs`), the `mod deeper;` it declares in turn (`src/checks/deeper.rs`), and a bare `mod tests;` (`src/tests.rs`). A file that a crate root declares plainly is compared, even when another root declares it `#[cfg(test)]`. This holds when the run names only the module files, without the crate roots that declare them.

## How to get to it (user POV)

- Run `./dryer src` in a Rust crate, and read which spans the pairs name.
- To see every function dryer compares, run `./dryer --threshold 0 --min-lines 1 --min-nodes 1 src`. Every compared function then pairs with every other one.

## Driving it with verify-dryer

Preconditions:

- `$vd doctor` prints `doctor: ok`.
- `project=$($vd project empty)` for each recipe. `T` is the transcript path for the feature.
- Each crate needs a `Cargo.toml` with `[package]` at its top folder:

```bash
printf '[package]\nname = "demo"\nversion = "0.1.0"\n' | $vd put "$project" Cargo.toml
```

**test-code-pair.** Put this file, then run `$vd drive "$project" "$T" src`.

```bash
$vd put "$project" src/lib.rs <<'EOF'
pub fn alpha(xs: Vec<i32>) -> Vec<i32> {
    let ys = filter(xs, odd);
    let zs = map(ys, inc);
    sorted(zs)
}

pub fn beta(items: Vec<i32>) -> Vec<i32> {
    let kept = filter(items, even);
    let moved = map(kept, dec);
    sorted(moved)
}

#[test]
fn totals_a_list() {
    let xs = vec![1, 2, 3];
    let got = total(&xs);
    assert_eq!(got, 6);
    assert!(got > 0);
}

#[test]
fn totals_another_list() {
    let items = vec![4, 5, 6];
    let sum = total(&items);
    assert_eq!(sum, 15);
    assert!(sum > 0);
}
EOF
```

Pass: exit `0`; stdout is one `DUPLICATE score=1.00` block, `src/lib.rs:1-5` with `src/lib.rs:7-11`. No span starts at line 14 or 22, the two tests.

**test-code-attributes.** Put these two files, then run `$vd drive "$project" "$T" --threshold 0 --min-lines 1 --min-nodes 1 src`.

```bash
$vd put "$project" src/lib.rs <<'EOF'
pub fn kept() {}

#[test]
fn t_test() {}

#[tokio::test]
async fn t_tokio() {}

#[cfg(test)]
mod checks {
    fn t_in_mod() {}
}

#[test_case(1)]
fn t_test_case(n: i32) {}

#[cfg(not(test))]
pub fn c_not_test() {}

#[cfg(any(test, feature = "x"))]
pub fn c_any_test() {}

#[test_cases]
pub fn c_look_alike() {}

mod only_tests;
EOF
printf '#![cfg(test)]\n\npub fn t_file() {}\n' | $vd put "$project" src/only_tests.rs
```

Pass: exit `0`; stdout has 6 `DUPLICATE` blocks, and every span is one of `src/lib.rs:1-1` (`kept`), `src/lib.rs:18-18` (`c_not_test`), `src/lib.rs:21-21` (`c_any_test`), and `src/lib.rs:24-24` (`c_look_alike`). No span names line 4, 7, 11, or 15, or `src/only_tests.rs`.

**test-code-module-files.** Put these files:

```bash
$vd put "$project" src/lib.rs <<'EOF'
pub fn tick() -> i32 {
    1
}

mod util;

#[cfg(test)]
mod checks;

mod tests;

#[cfg(test)]
mod shared;
EOF
printf 'fn main() {\n    println!("{}", demo::tick());\n}\n\nmod shared;\n' | $vd put "$project" src/main.rs
printf 'mod deeper;\n\nfn checks_sample() -> i32 {\n    super::tick()\n}\n' | $vd put "$project" src/checks.rs
printf 'fn deeper_probe() -> i32 {\n    2\n}\n' | $vd put "$project" src/checks/deeper.rs
printf 'fn tests_probe() -> i32 {\n    3\n}\n' | $vd put "$project" src/tests.rs
printf 'pub fn util_fn() -> i32 {\n    4\n}\n' | $vd put "$project" src/util.rs
printf 'pub fn shared_fn() -> i32 {\n    5\n}\n' | $vd put "$project" src/shared.rs
```

Then run `$vd drive "$project" "$T" --threshold 0 --min-lines 1 --min-nodes 1 src`. Pass: exit `0`; stdout has 6 `DUPLICATE` blocks, and every span is in `src/lib.rs`, `src/main.rs`, `src/util.rs`, or `src/shared.rs`. No span names `src/checks.rs`, `src/checks/deeper.rs`, or `src/tests.rs`.

Then run `$vd drive "$project" "$T" --threshold 0 --min-lines 1 --min-nodes 1 src/checks.rs src/checks/deeper.rs src/tests.rs src/util.rs src/shared.rs`. Pass: exit `0`; stdout is one `DUPLICATE` block, naming `src/shared.rs:1-3` and `src/util.rs:1-3`.

## Gotchas

- dryer reads the crate roots (`src/lib.rs`, `src/main.rs`, `src/bin/...`) and the module files between a root and a file from disk, even when the run names only that file. A file with no `Cargo.toml` above it, or one no module declares, is compared as before.
- A bare `mod tests;` is test code by its name, as an inline `mod tests { }` is, although rustc compiles that file in a normal build.
- The rule is crapper's (`crapper --no-coverage` leaves the same functions out). Functions inside `proptest! { }` or `quickcheck! { }` are never compared: tree-sitter reads a macro body as tokens.
