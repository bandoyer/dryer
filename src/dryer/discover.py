"""Find source files and decide which language each one is written in.

The extensions and the skipped directories match crapper and mutator, with
`.cljd` added because dry4clj reads it.

A C# test project is found by the rule crapper and skillflow's measure use
too (bandoyer/skillflow#270 and #271): a folder whose name ends in `Test` or
`Tests` or has a dot-separated part `Test` or `Tests`, or a `.csproj` that marks
itself a test project. The nearest folder at or above a `.cs` file that holds a
`.csproj` decides the second. Change the three together.
"""

import os
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

EXTENSIONS = {
    ".clj": "clojure",
    ".cljc": "clojure",
    ".cljs": "clojure",
    ".cljd": "clojure",
    ".bb": "clojure",
    ".java": "java",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".rs": "rust",
    ".py": "python",
    ".cs": "csharp",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "target",
    "dist",
    "build",
    "out",
    "coverage",
    ".metrics",
    "testdata",
    "__pycache__",
    ".clj-kondo",
}

TEST_DIRS = {"test", "tests", "spec", "specs", "__tests__"}

# A PackageReference to one of these marks a C# test project. NuGet ids ignore case.
# Microsoft.Testing.Platform isn't one: a test runner references it as a library.
_CSHARP_TEST_PACKAGES = {
    "microsoft.net.test.sdk",
    "nunit",
    "xunit",
    "xunit.v3",
    "mstest.testframework",
}


def language_of(path: str | Path) -> str | None:
    file_path = Path(path)
    name = file_path.name
    if name.endswith(".d.ts"):
        return None
    return EXTENSIONS.get(file_path.suffix)


def _csharp_test_folder(name: str) -> bool:
    return name.endswith(("Test", "Tests")) or not {"Test", "Tests"}.isdisjoint(name.split("."))


def _mstest_sdk(root) -> bool:
    """`<Project Sdk="MSTest.Sdk">`, with or without a `/version`."""

    sdks = root.get("Sdk", "").split(";")
    return any(sdk.split("/")[0].strip().lower() == "mstest.sdk" for sdk in sdks)


def _marks_a_test_project(project: Path) -> bool:
    try:
        root = ElementTree.parse(project).getroot()
    except (OSError, ElementTree.ParseError):
        return False
    if _mstest_sdk(root):
        return True
    for element in root.iter():
        tag = element.tag.rpartition("}")[2]
        if tag == "IsTestProject" and (element.text or "").strip().lower() == "true":
            return True
        package = element.get("Include", "").strip().lower()
        if tag == "PackageReference" and package in _CSHARP_TEST_PACKAGES:
            return True
    return False


@lru_cache(maxsize=None)
def _in_marked_test_project(folder: Path) -> bool:
    for current in (folder, *folder.parents):
        projects = sorted(current.glob("*.csproj"))
        if projects:
            return any(_marks_a_test_project(project) for project in projects)
    return False


def _csharp_test_file(file_path: Path) -> bool:
    if any(_csharp_test_folder(name) for name in file_path.parent.parts):
        return True
    return _in_marked_test_project(file_path.resolve().parent)


def is_test_file(path: str | Path) -> bool:
    file_path = Path(path)
    name = file_path.name
    if file_path.suffix == ".cs" and _csharp_test_file(file_path):
        return True
    if name.endswith("_test.go"):
        return True
    if name.endswith(("_test.clj", "_test.cljc", "_test.cljs", "_test.cljd", "_test.bb")):
        return True
    if name.endswith(
        (
            ".test.ts",
            ".spec.ts",
            ".test.tsx",
            ".spec.tsx",
            ".test.mts",
            ".spec.mts",
            ".test.cts",
            ".spec.cts",
        )
    ):
        return True
    if name == "conftest.py":
        return True
    if name.endswith("_test.py") or (name.startswith("test_") and name.endswith(".py")):
        return True
    return any(part in TEST_DIRS for part in file_path.parts)


def _skipped_dir(name: str) -> bool:
    return name in SKIP_DIRS or name in TEST_DIRS


def _walk(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not _skipped_dir(name)]
        for name in filenames:
            path = Path(dirpath) / name
            if language_of(path) is None or is_test_file(path):
                continue
            found.append(path)
    return found


def iter_source_files(roots: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for root in roots:
        for path in _walk(root):
            files.add(path.resolve())
    return sorted(files, key=lambda path: path.as_posix())
