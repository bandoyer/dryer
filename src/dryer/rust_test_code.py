"""Which Rust functions and files are test code, so dryer leaves them out.

A function is test code when it sits in a `mod tests`, or when it, or a `mod`,
`impl`, or file around it, has a test attribute. A test attribute is one whose
path ends in `test` (`#[test]`, `#[tokio::test]`), one of `#[rstest]`,
`#[test_case]`, `#[test_matrix]`, `#[proptest]`, `#[property_test]`,
`#[wasm_bindgen_test]`, and `#[quickcheck]` (bare or with a path), or a `cfg`
that holds only in a test build (`test`, or `all(...)` with such a part). An
inner `#![cfg(test)]` marks the file or `mod` body it starts.

A module declared with `mod x;` keeps its body in another file, so dryer
follows the crate's module tree from its roots (`src/lib.rs`, `src/main.rs`,
`src/bin/...`) by rustc's rules, and leaves out a file that every root reaches
only through test code. A bare `mod tests;` counts as test code by its name,
as an inline `mod tests { }` does, although rustc compiles it in a normal
build.

This is crapper's rule, ported from `src/crapper/languages/rust.py` at
bandoyer/crapper 5f12def (#43 and #48), so the two tools agree on what Rust
test code is. Change both together.
"""

from __future__ import annotations

import re
from pathlib import Path

from dryer.treesitter import child_of_type, descendants, node_text, parse

_TEST_ATTRIBUTES = {
    "test",
    "rstest",
    "test_case",
    "test_matrix",
    "proptest",
    "property_test",
    "wasm_bindgen_test",
    "quickcheck",
}
_BEFORE_ITEM = {"attribute_item", "line_comment", "block_comment"}
_BODIES = {"source_file", "declaration_list"}
_PACKAGE_BLOCK = re.compile(r"(?m)^\[package\]")


def _ancestor_mods(data: bytes, node) -> list[str]:
    names: list[str] = []
    current = node.parent
    while current is not None:
        if current.type == "mod_item":
            ident = child_of_type(current, "identifier")
            if ident is not None:
                names.append(node_text(data, ident))
        current = current.parent
    names.reverse()
    return names


def _predicates(data: bytes, predicates):
    """Each predicate in a `cfg` list, `(...)`, as its name and its own list, or None."""

    items = predicates.children
    for item, following in zip(items, [*items[1:], None]):
        if item.type == "identifier":
            nested = following if following is not None and following.type == "token_tree" else None
            yield node_text(data, item), nested


def _test_only(data: bytes, predicates) -> bool:
    """A `cfg` predicate list that holds only in a test build: `test`, or `all(...)` with such a part.

    Unlike crapper's, it keeps the `all(...)` lists still to read on a list, not
    the call stack, so a deeply nested `cfg` can't raise `RecursionError`."""

    lists = [predicates]
    while lists:
        for name, nested in _predicates(data, lists.pop()):
            if name == "test" and nested is None:
                return True
            if name == "all" and nested is not None:
                lists.append(nested)
    return False


def _is_test_attribute(data: bytes, attribute) -> bool:
    path = "".join(node_text(data, attribute.children[0]).split())
    if path == "cfg":
        predicates = child_of_type(attribute, "token_tree")
        return predicates is not None and _test_only(data, predicates)
    return path.split("::")[-1] in _TEST_ATTRIBUTES


def _attribute_items(node):
    """A node's attribute items: inner `#![...]` ones when it is a file or a `mod`
    body, and outer ones written before it, with any comments between them."""

    if node.type in _BODIES:
        yield from (child for child in node.children if child.type == "inner_attribute_item")
    current = node.prev_sibling
    while current is not None and current.type in _BEFORE_ITEM:
        yield current
        current = current.prev_sibling


def _attributes(node):
    for item in _attribute_items(node):
        attribute = child_of_type(item, "attribute")
        if attribute is not None:
            yield attribute


def _in_test_code(data: bytes, node) -> bool:
    """The function, or a `mod`, `impl`, or file around it, has a test attribute."""

    current = node
    while current is not None:
        if any(_is_test_attribute(data, attribute) for attribute in _attributes(current)):
            return True
        current = current.parent
    return False


def is_test_item(data: bytes, node) -> bool:
    """The item sits in a `mod tests`, or it, or a `mod`, `impl`, or file around it, has a test attribute."""

    return "tests" in _ancestor_mods(data, node) or _in_test_code(data, node)


def _path_attribute(data: bytes, node) -> str | None:
    """The file a `#[path = "..."]` on the item names, or None."""

    for attribute in _attributes(node):
        if node_text(data, attribute.children[0]) != "path":
            continue
        for item in descendants(attribute):
            if item.type == "string_content":
                return node_text(data, item)
    return None


def _declarations(data: bytes, tree):
    """Each `mod x;` in a parsed file (a `mod` with no body here), with its name
    as a file name: `mod r#type;` loads `type.rs`."""

    for node in descendants(tree.root_node):
        if node.type == "mod_item" and child_of_type(node, "declaration_list") is None:
            ident = child_of_type(node, "identifier")
            if ident is not None:
                yield node, node_text(data, ident).removeprefix("r#")


def _module_files(module: Path, folder: Path):
    """Each `mod x;` in a module file, by rustc's rules: the file it loads, the
    folder where that file's own declarations resolve, and whether the
    declaration is test code. `folder` is where this file's declarations
    resolve: beside a crate root, `mod.rs`, or `#[path]` file, and under
    `a/x/` for a plain module file `a/x.rs`. Only a regular file is yielded,
    so the walk never reads a FIFO or a device a `#[path]` names."""

    try:
        data, tree = parse(module.read_text(encoding="utf-8", errors="replace"), "rust")
    except OSError:
        return
    for node, name in _declarations(data, tree):
        inline = [part.removeprefix("r#") for part in _ancestor_mods(data, node)]
        base = folder.joinpath(*inline)
        test = name == "tests" or is_test_item(data, node)
        path = _path_attribute(data, node)
        if path is not None:
            loaded = ((base if inline else module.parent) / path).resolve()
            candidates = [(loaded, loaded.parent)]
        else:
            candidates = [(base / f"{name}.rs", base / name), (base / name / "mod.rs", base / name)]
        for loaded, below in candidates:
            if loaded.is_file():
                yield loaded.resolve(), below.resolve(), test
                break


def _crate_roots(crate_root: Path) -> list[Path]:
    src = crate_root / "src"
    found = [src / "lib.rs", src / "main.rs", *(src / "bin").glob("*.rs"), *(src / "bin").glob("*/main.rs")]
    return [root.resolve() for root in found if root.is_file()]


def _ways_to(target: Path, roots: list[Path]):
    """Whether each declaration that loads `target` is reached through test code,
    walking the module tree down from the crate roots. Below the roots, the walk
    opens only a module whose folder holds `target`, and each module once per
    test-code state, so a `#[path]` cycle ends."""

    walk = [(root, root.parent, False) for root in roots]
    seen = set(walk)
    while walk:
        module, folder, test = walk.pop()
        for loaded, below, declared_test in _module_files(module, folder):
            through_test = test or declared_test
            if loaded == target:
                yield through_test
            elif target.is_relative_to(below) and (loaded, below, through_test) not in seen:
                seen.add((loaded, below, through_test))
                walk.append((loaded, below, through_test))


def _test_only_file(file: Path, crate_root: Path) -> bool:
    """At least one crate root reaches the file, and only through test code."""

    target = file.resolve()
    roots = _crate_roots(crate_root)
    if target in roots:
        return False
    reached = False
    for through_test in _ways_to(target, roots):
        if not through_test:
            return False
        reached = True
    return reached


def _package(cargo: Path) -> bool:
    """The `Cargo.toml` has a `[package]`. Unlike crapper, dryer reads one that
    isn't UTF-8 with replacement characters, and one it can't open as having none."""

    try:
        return _PACKAGE_BLOCK.search(cargo.read_text(encoding="utf-8", errors="replace")) is not None
    except OSError:
        return False


def _crate_root(file: Path) -> Path | None:
    """The folder of the nearest `Cargo.toml` above the file that has a `[package]`."""

    for folder in file.resolve().parents:
        cargo = folder / "Cargo.toml"
        if cargo.is_file() and _package(cargo):
            return folder
    return None


def is_test_only_file(path: str) -> bool:
    """The file's crate reaches it only through test code, such as `#[cfg(test)] mod checks;`."""

    file = Path(path)
    crate_root = _crate_root(file)
    return crate_root is not None and _test_only_file(file, crate_root)
