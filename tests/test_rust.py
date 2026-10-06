"""Rust test code is not compared (#25).

The cases are crapper's (tests/test_rust.py at bandoyer/crapper 5f12def), so
the two tools agree on which Rust functions are test code.
"""

import inspect
import os
import re
import sys
import threading
from pathlib import Path

import pytest

from dryer.extract import entries_in_source


def _compared(source: str, path: str = "/tmp/lib.rs") -> list[str]:
    """The names of the functions dryer compares in one Rust source."""

    entries, _ = entries_in_source("rust", source, path, "lib.rs")
    return [re.search(r"fn (\w+)", source[entry.offset :]).group(1) for entry in entries]


@pytest.mark.parametrize(
    "item",
    [
        "#[test]\nfn hidden() {}",
        "#[should_panic]\n#[test]\nfn hidden() {}",
        "#[test]\n#[should_panic]\nfn hidden() {}",
        "/// Checks the dial.\n#[test]\n// keep\nfn hidden() {}",
        "#[tokio::test]\nasync fn hidden() {}",
        "#[async_std::test]\nasync fn hidden() {}",
        "#[rstest]\nfn hidden() {}",
        "#[cfg(test)]\nfn hidden() {}",
        "#[cfg(all(test, feature = \"x\"))]\nfn hidden() {}",
        "#[cfg(all(unix, all(test, feature = \"x\")))]\nfn hidden() {}",
        "#[cfg(test)]\nmod checks {\n    fn hidden() {}\n}",
        "#[cfg(test)]\nimpl Dial {\n    fn hidden(&self) {}\n}",
        "mod checks {\n    #![cfg(test)]\n    fn hidden() {}\n}",
    ],
)
def test_rust_test_code_is_not_compared(item):
    """A test function, or one in test-only code, is not compared."""

    assert _compared(f"pub fn kept() {{}}\n\n{item}\n") == ["kept"]


@pytest.mark.parametrize(
    "item",
    [
        "#[test_case(1)]\nfn hidden(n: i32) {}",
        "#[test_case::test_case(2)]\nfn hidden(n: i32) {}",
        "#[test_case(1)]\n#[test_case(2)]\nfn hidden(n: i32) {}",
        "#[test_matrix([1, 2])]\nfn hidden(n: i32) {}",
        "#[proptest]\nfn hidden(n: u8) {}",
        "#[property_test]\nfn hidden(n: u8) {}",
        "#[wasm_bindgen_test]\nfn hidden() {}",
        "#[wasm_bindgen_test::wasm_bindgen_test]\nfn hidden() {}",
        "#[quickcheck]\nfn hidden(n: u8) -> bool {\n    n > 0\n}",
        "#[quickcheck_macros::quickcheck]\nfn hidden(n: u8) -> bool {\n    n > 0\n}",
    ],
)
def test_rust_functions_with_other_test_attributes_are_not_compared(item):
    """test-case, proptest, wasm-bindgen-test, and quickcheck tests are test code."""

    assert _compared(f"pub fn kept() {{}}\n\n{item}\n") == ["kept"]


def test_functions_in_a_test_macro_body_are_not_listed():
    source = (
        "pub fn kept() {}\n\n"
        "proptest! {\n    #[test]\n    fn hidden(n in 0..10u8) {\n        if n > 1 {}\n    }\n}\n\n"
        "quickcheck! {\n    fn also_hidden(n: u8) -> bool {\n        n > 0\n    }\n}\n"
    )
    assert _compared(source) == ["kept"]


@pytest.mark.parametrize(
    "attribute",
    [
        "#[must_use]",
        "#[inline]",
        "#[cfg(not(test))]",
        "#[cfg(any(test, feature = \"x\"))]",
        "#[cfg(feature = \"x\")]",
        "#[cfg(all(unix, feature = \"x\"))]",
        "#[testing::helper]",
        "#[attest]",
        "#[test_helper]",
        "#[wasm_bindgen]",
        "#[test_cases]",
        "#[quickcheck_helper]",
    ],
)
def test_rust_functions_with_other_attributes_are_compared(attribute):
    assert _compared(f"{attribute}\npub fn kept() {{}}\n") == ["kept"]


def test_a_rust_file_marked_test_only_compares_nothing():
    assert _compared("#![cfg(test)]\n\npub fn helper() {}\n") == []


def test_other_inner_attributes_keep_a_rust_function_compared():
    source = "#![allow(dead_code)]\n\nmod gears {\n    #![allow(unused)]\n    pub fn kept() {}\n}\n"
    assert _compared(source) == ["kept"]


# crapper #45's crate: test-only modules declared with `mod x;` and kept in
# their own files. Each module file holds one function. rustc compiles the
# TEST_ONLY files only in a test build; it compiles the CODE files in a normal
# build, except tests.rs (a `mod tests` is test code by its name) and
# orphan.rs, which no module declares.
TREE = {
    "Cargo.toml": '[package]\nname = "tree"\nversion = "0.1.0"\nedition = "2021"\n',
    "src/lib.rs": """pub fn tick() -> i32 {
    1
}

pub mod outer;
mod util;

#[cfg(test)]
mod checks;

#[cfg(test)]
mod fixtures;

#[cfg(test)]
mod inline {
    mod leaf;
}

#[cfg(test)]
#[path = "support/helpers.rs"]
mod helpers;

#[cfg(all(test, feature = "x"))]
mod gated;

mod tests;

#[cfg(not(test))]
mod real;

#[cfg(test)]
mod shared;
""",
    "src/main.rs": "fn main() {}\n\nmod shared;\n\n#[cfg(test)]\nmod cli_checks;\n",
    "src/checks.rs": "mod deeper;\n\nfn checks_sample() -> i32 {\n    1\n}\n",
    "src/checks/deeper.rs": "fn deeper_probe() {}\n",
    "src/fixtures/mod.rs": "fn fixtures_probe() {}\n",
    "src/outer.rs": "pub fn outer_fn() {}\n\n#[cfg(test)]\nmod inner;\n",
    "src/outer/inner.rs": "fn inner_probe() {}\n",
    "src/inline/leaf.rs": "fn leaf_probe() {}\n",
    "src/support/helpers.rs": "fn helpers_probe() {}\n",
    "src/gated.rs": "fn gated_probe() {}\n",
    "src/tests.rs": "fn tests_probe() {}\n",
    "src/cli_checks.rs": "fn cli_probe() {}\n",
    "src/util.rs": "pub fn util_fn() {}\n",
    "src/real.rs": "pub fn real_fn() {}\n",
    "src/shared.rs": "pub fn shared_fn() {}\n",
    "src/orphan.rs": "pub fn orphan_fn() {}\n",
}

TEST_ONLY = [
    "src/checks.rs",
    "src/fixtures/mod.rs",
    "src/outer/inner.rs",
    "src/checks/deeper.rs",
    "src/inline/leaf.rs",
    "src/support/helpers.rs",
    "src/gated.rs",
    "src/tests.rs",
    "src/cli_checks.rs",
]

CODE = {
    "src/lib.rs": ["tick"],
    "src/main.rs": ["main"],
    "src/outer.rs": ["outer_fn"],
    "src/util.rs": ["util_fn"],
    "src/real.rs": ["real_fn"],
    "src/shared.rs": ["shared_fn"],
    "src/orphan.rs": ["orphan_fn"],
}


def _write_crate(root: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _listed(root: Path, relative: str) -> list[str]:
    """Function names as dryer compares them: the CLI passes an absolute path."""

    path = root / relative
    return _compared(path.read_text(encoding="utf-8"), path.as_posix())


@pytest.mark.parametrize("relative", TEST_ONLY)
def test_a_test_only_module_in_its_own_file_is_not_compared(tmp_path, monkeypatch, relative):
    """The module tree, not the file alone, says the file is test code."""

    crate = _write_crate(tmp_path / "tree", TREE)
    monkeypatch.chdir(tmp_path)
    assert _listed(crate, relative) == []


@pytest.mark.parametrize("relative", sorted(CODE))
def test_a_module_file_a_crate_root_compiles_is_compared(tmp_path, monkeypatch, relative):
    crate = _write_crate(tmp_path / "tree", TREE)
    monkeypatch.chdir(tmp_path)
    assert _listed(crate, relative) == CODE[relative]


def test_a_missing_module_file_or_a_module_that_loads_itself_ends_the_walk(tmp_path):
    crate = _write_crate(
        tmp_path / "loops",
        {
            "Cargo.toml": '[package]\nname = "loops"\nversion = "0.1.0"\n',
            "src/lib.rs": (
                '#[cfg(test)]\nmod gone;\n\n#[path = "lib.rs"]\nmod again;\n\n'
                '#[path = "lost/missing.rs"]\nmod lost;\n\npub fn tick() {}\n'
            ),
            "src/stray.rs": "pub fn stray() {}\n",
            "src/lost/stray.rs": "pub fn lost_stray() {}\n",
        },
    )
    assert _listed(crate, "src/lib.rs") == ["tick"]
    assert _listed(crate, "src/stray.rs") == ["stray"]
    assert _listed(crate, "src/lost/stray.rs") == ["lost_stray"]


CARGO = '[package]\nname = "edges"\nversion = "0.1.0"\n'


@pytest.mark.parametrize(
    "files, relative, names",
    [
        pytest.param(
            {"src/bin/tool/main.rs": "fn main() {}\n\n#[cfg(test)]\nmod checks;\n", "src/bin/tool/checks.rs": "fn hidden() {}\n"},
            "src/bin/tool/checks.rs",
            [],
            id="a binary root's test-only module",
        ),
        pytest.param(
            {"src/lib.rs": '#[cfg(test)]\n#[path = "../testsupport/helpers.rs"]\nmod helpers;\n', "testsupport/helpers.rs": "fn hidden() {}\n"},
            "testsupport/helpers.rs",
            [],
            id="a #[path] from a root out of src",
        ),
        pytest.param(
            {"src/lib.rs": "pub mod outer;\n", "src/outer.rs": '#[cfg(test)]\n#[path = "outer/impl_checks.rs"]\nmod checks;\n', "src/outer/impl_checks.rs": "fn hidden() {}\n"},
            "src/outer/impl_checks.rs",
            [],
            id="a #[path] in a plain module file, inside its folder",
        ),
        pytest.param(
            {"src/lib.rs": '#[cfg(test)]\nmod inline {\n    #[path = "p.rs"]\n    mod q;\n}\n', "src/inline/p.rs": "fn hidden() {}\n"},
            "src/inline/p.rs",
            [],
            id="a #[path] inside an inline module",
        ),
        pytest.param(
            {"src/lib.rs": '#[cfg(test)]\n#[path = "support/helpers.rs"]\nmod helpers;\n', "src/support/helpers.rs": "mod sub;\n", "src/support/sub.rs": "fn hidden() {}\n"},
            "src/support/sub.rs",
            [],
            id="a #[path] file's own module resolves beside it",
        ),
        pytest.param(
            {"src/lib.rs": "pub mod outer;\n", "src/outer.rs": '#[cfg(test)]\n#[path = "sibling.rs"]\nmod checks;\n', "src/sibling.rs": "pub fn kept() {}\n"},
            "src/sibling.rs",
            ["kept"],
            id="a #[path] out of a plain module's folder is not followed",
        ),
        pytest.param(
            {"src/lib.rs": "#[cfg(test)]\nmod r#type;\n", "src/type.rs": "fn hidden() {}\n"},
            "src/type.rs",
            [],
            id="a raw-identifier module name",
        ),
        pytest.param(
            {"src/lib.rs": "#[cfg(test)]\nmod r#async {\n    mod leaf;\n}\n", "src/async/leaf.rs": "fn hidden() {}\n"},
            "src/async/leaf.rs",
            [],
            id="a raw-identifier inline module",
        ),
        pytest.param(
            {"src/lib.rs": "#[cfg(test)]\nmod helpers {\n    fn inside() {}\n}\n", "src/helpers.rs": "pub fn kept() {}\n"},
            "src/helpers.rs",
            ["kept"],
            id="an inline module loads no file of its name",
        ),
        pytest.param(
            {"src/lib.rs": "#[cfg(test)]\nmod checks;\n", "src/checks.rs": "pub fn kept() {}\n", "src/bin/checks.rs": "fn main() {}\n"},
            "src/bin/checks.rs",
            ["main"],
            id="a binary root of the same name is compared",
        ),
    ],
)
def test_module_tree_edges(tmp_path, files, relative, names):
    crate = _write_crate(tmp_path / "edges", {"Cargo.toml": CARGO, **files})
    assert _listed(crate, relative) == names


def test_the_module_walk_does_not_deepen_the_stack_per_module(tmp_path):
    """A chain of 150 nested modules is walked with fewer than 100 spare stack frames."""

    depth = 150
    files = {"Cargo.toml": CARGO, "src/lib.rs": "#[cfg(test)]\nmod m;\n"}
    for level in range(1, depth):
        files["src/" + "m/" * (level - 1) + "m.rs"] = "mod m;\n"
    deepest = "src/" + "m/" * (depth - 1) + "m.rs"
    files[deepest] = "fn hidden() {}\n"
    crate = _write_crate(tmp_path / "deep", files)
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(len(inspect.stack()) + 100)
    try:
        listed = _listed(crate, deepest)
    finally:
        sys.setrecursionlimit(limit)
    assert listed == []


def test_a_path_that_names_no_regular_file_is_not_opened(tmp_path):
    """A `#[path]` to a FIFO would block the walk's read forever."""

    crate = _write_crate(
        tmp_path / "pipes",
        {"Cargo.toml": CARGO, "src/lib.rs": '#[cfg(test)]\n#[path = "pipe"]\nmod piped;\n', "src/other.rs": "pub fn kept() {}\n"},
    )
    os.mkfifo(crate / "src" / "pipe")
    listed = []
    walk = threading.Thread(target=lambda: listed.extend(_listed(crate, "src/other.rs")), daemon=True)
    walk.start()
    walk.join(10)
    assert listed == ["kept"]


def test_an_unreadable_module_file_ends_its_branch_of_the_walk(tmp_path):
    crate = _write_crate(
        tmp_path / "locked",
        {"Cargo.toml": CARGO, "src/lib.rs": "pub mod outer;\n", "src/outer.rs": "#[cfg(test)]\nmod inner;\n", "src/outer/inner.rs": "pub fn kept() {}\n"},
    )
    (crate / "src" / "outer.rs").chmod(0)
    if os.access(crate / "src" / "outer.rs", os.R_OK):
        pytest.skip("this user can read a file with mode 0")
    assert _listed(crate, "src/outer/inner.rs") == ["kept"]


def test_a_cargo_toml_that_is_not_utf8_is_still_read(tmp_path):
    """dryer reads Cargo.toml with replacement characters; crapper exits 1 here."""

    crate = _write_crate(
        tmp_path / "bytes",
        {"src/lib.rs": "#[cfg(test)]\nmod checks;\n\npub fn tick() {}\n", "src/checks.rs": "fn hidden() {}\n"},
    )
    (crate / "Cargo.toml").write_bytes(b'[package]\nname = "b\xff"\nversion = "0.1.0"\n')
    assert _listed(crate, "src/lib.rs") == ["tick"]
    assert _listed(crate, "src/checks.rs") == []


def test_an_unreadable_cargo_toml_counts_as_no_package(tmp_path):
    crate = _write_crate(
        tmp_path / "locked",
        {"Cargo.toml": CARGO, "src/lib.rs": "#[cfg(test)]\nmod checks;\n", "src/checks.rs": "pub fn kept() {}\n"},
    )
    (crate / "Cargo.toml").chmod(0)
    if os.access(crate / "Cargo.toml", os.R_OK):
        pytest.skip("this user can read a file with mode 0")
    assert _listed(crate, "src/checks.rs") == ["kept"]
