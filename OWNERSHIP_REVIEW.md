# Dryer ownership review

Reviewed on October 4, 2026, at commit `66ff6d21a42c04afcad89c78a80066176d1294b0` in `bandoyer/dryer`, forked from `unclebob/dryer`.

Dryer is small enough to maintain without a rewrite. Its separation of discovery, extraction, normalization, comparison, and reporting is useful. Before treating its output as dependable across the advertised languages, fix the cases where normalization loses executable structure and where the Clojure reader drops valid input. Optimize comparison after those correctness fixes.

This is a full repository review of the recorded commit, including source, tests, packaging, launch scripts, and documentation. It is not a comparison against upstream. Findings below propose changes; this PR changes only this report. One initial review and one evidence/report check were used. No implementation repair pass was needed.

## Verification and limits

- `.venv/bin/python -m pytest -q`: **80 passed in 0.98 seconds**.
- Environment: Linux, Python 3.14.8, pytest 9.1.1, tree-sitter 0.26.0, tree-sitter-language-pack 1.21.0. Pytest was added to the existing virtual environment.
- Inspected all 12 production Python files and the tracked support files. Test inspection focused on behavior and boundary assertions across the three test files, alongside the full suite. Production code has 1,902 lines; tests have 1,311 lines. Counts exclude this report and installed dependencies.
- Ran focused extraction, normalization, reader, empty-snapshot, and configuration probes. Benchmarked comparison and fingerprint storage without changing production code.
- The language parser cache was already usable. A cold offline installation, other operating systems, and every Python version allowed by `requires-python` were not tested. Source fixtures test parsing, not compilation by all six language toolchains.

Priorities: **P1** can invalidate a core result or stop normal operation. **P2** is a narrower correctness or compatibility defect. Performance and design proposals remain advice unless a required workload establishes a limit.

## Act on

These findings have a concrete trigger and an observed result that conflicts with the tool's stated behavior.

### D1. Preserve executable expressions and operators during normalization: P1

The README says call names, operators, and tree shape remain. Two reproducible cases contradict that contract:

| Input pair | Observed similarity | Problem |
| --- | --- | --- |
| TypeScript functions returning `` `${approve(x)}` `` and `` `${reject(x)}` `` | `1.0` | The whole template string becomes a literal, including the call inside it. |
| Python functions returning `x in y` and `x is y` | `1.0` | Neither `in` nor `is` is in the preserved operator set. |

These are extraction-level examples. Use `--min-lines 1 --min-nodes 1` when reproducing them through the CLI, or place them in longer functions. Calling `entries_in_source` and then `jaccard` reproduces the scores directly.

Evidence: [literal node types](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/astnorm.py#L34), [operator set](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/astnorm.py#L74), [_is_literal](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/astnorm.py#L158), and [_try_leaf](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/astnorm.py#L197). Python interpolation has a special case; TypeScript interpolation does not.

Smallest repair: keep interpolation subtrees and retain all supported comparison operators, including compound Python operators. Preserve literal text normalization. Add paired tests that change only the embedded callee or operator and require a score below `1.0`, alongside renamed-local tests that still score `1.0`.

### D2. Handle valid Clojure reader syntax without stopping or adding forms: P1

`(defn f [] #'g)` produces `1: expected a symbol` and no candidate. `read_source` then stops, so valid definitions later in the file are also omitted. Var quote is valid Clojure syntax, not an unreadable source file.

Auto-resolved namespaced maps also change structure incorrectly. These two forms should normalize the same way because namespace names and keywords are incidental here:

```clojure
(defn f [] #::alias{:x 1})
(defn f [] #:alias{:x 1})
```

The first normalization contains an extra `:symbol` before the map. `_read_map_qualifier` consumes the second colon but leaves `alias` as another form.

Evidence: [reader dispatch and map qualifiers](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/clojure_read.py#L322), [dispatch table](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/clojure_read.py#L352), and [read_source](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/clojure_read.py#L397). The [Clojure reader reference](https://clojure.org/reference/reader) documents var quote and auto-resolved map namespaces.

Smallest repair: implement var quote as a wrapper and consume the complete map qualifier. Add fixtures with a valid function after each reader form. Also add a reader-conformance table so unsupported syntax produces an explicit diagnostic instead of unnoticed structural changes. Do not evaluate source to read it.

### D3. Record actual Clojure end positions: P2

This form spans three lines, but its reported span is `(1, 2)`:

```clojure
(defn f [x]
  (inc x)
)
```

`max_line` uses the start line of the last child. Collection closing delimiters and the end of multiline string literals are not recorded. This gives incorrect report locations and can remove a qualifying form at the `--min-lines` boundary.

Evidence: [Lit and Coll](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/clojure_read.py#L52), [_close_coll](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/clojure_read.py#L73), [max_line](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/clojure_read.py#L427), and [minimum-line filtering](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/scan.py#L21).

Smallest repair: retain end positions while reading strings and collections. Use the top-level form's actual end position. Test closing-only lines and multiline string literals, including a form exactly at the minimum-line count.

### D4. Do not identify a function solely by its line range: P2

For this valid Java source, extraction finds two entries but `find_duplicates(entries, 0)` returns no pairs:

```java
class A { int a(){return 1+2;} int b(){return 3+4;} }
```

Both functions occupy the same file and line. `_same_span` discards the pair as though it were the same function. This affects compact source and explicit low `--min-lines` settings.

Evidence: [_same_span](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/scan.py#L44), [Entry](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/model.py#L26), and [tree entry construction](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/extract.py#L155).

Smallest repair: retain byte offsets for identity and keep line ranges for presentation. Test two distinct functions on one line and repeated references to the exact same source node separately.

### D5. Exclude Java anonymous-class methods in field initializers: P2

The README excludes methods inside anonymous classes. This case still produces a candidate:

```java
class A {
  Runnable r = new Runnable() {
    public void run() { if (true) return; }
  };
}
```

The exclusion checks for enclosing methods, constructors, or lambdas. An anonymous class in a field initializer has none of those ancestors. The existing anonymous/local-class protection therefore covers only some placements.

Evidence: [_java_nodes](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/extract.py#L74). The equivalent bug exists in crapper and should receive the same fixture.

Smallest repair: detect anonymous-class ownership explicitly. Test field initializers and initializer blocks, while retaining named nested member classes.

### D6. Correct the declared parser dependency minimum: P2

`pyproject.toml` permits `tree-sitter-language-pack==0.7.0`, but `parser_for` unconditionally imports `download`. The downloaded 0.7.0 wheel's module exports only `SupportedLanguage`, `get_binding`, `get_language`, and `get_parser`; it has no `download` function.

That permitted dependency version cannot satisfy this import. The current 1.21.0 environment passes tests, which does not validate the declared lower bound. This was verified by inspecting the 0.7.0 wheel, not by claiming the full suite ran against it.

Evidence: [dependencies](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/pyproject.toml#L9) and [parser_for](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/treesitter.py#L7).

Smallest repair: establish and declare the earliest release that provides the APIs used, or support both APIs deliberately. Test the declared minimum and a current dependency set. Document grammar download/cache requirements and return a useful error when grammar provisioning fails.

### D7. Replace stale metrics after a successful empty full scan: P2

Put any existing result in `.metrics/dry.edn`, remove all source files, and run a full scan. The command exits `0` with `No source files to analyze.` and leaves the previous report untouched. A viewer can continue showing duplicates for deleted files.

Evidence: [run](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/cli.py#L286), which returns before [write_metrics](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/report.py#L70). A temporary-directory reproduction left a sentinel report unchanged.

Smallest repair: an empty successful full scan should write `{:candidates []}`. Decide separately how an empty filtered or `--changed` scan behaves, and document that distinction. Regression tests should start with a populated report, not only an empty directory.

## Consider

These improvements are useful, but their cost should follow measured workloads and ownership priorities.

### D8. Reduce pair-comparison work before changing the similarity metric

`find_duplicates` compares every pair within a language. `group[index + 1:]` also allocates a new list for each outer iteration. `jaccard` constructs both a union and an intersection for every comparison.

Measured on this machine with 40 distinct fingerprint strings per candidate, no matches, threshold `0.82`, and three runs per size:

| Candidates | Pair comparisons | Median time |
| ---: | ---: | ---: |
| 500 | 124,750 | 0.2117 s |
| 1,000 | 499,500 | 0.8534 s |
| 2,000 | 1,999,000 | 3.3896 s |

These are synthetic comparison-only measurements, not whole-project timings or promises about other machines.

Evidence: [find_duplicates](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/scan.py#L64) and [jaccard](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/shape.py#L104).

Start with index iteration and compute union size as `len(left) + len(right) - intersection_size`. For a positive threshold, reject pairs when `min(size_left, size_right) / max(size_left, size_right)` cannot reach it. Then evaluate an inverted fingerprint index if real repositories still need it. Verify identical candidate pairs, scores, and ordering. A high-duplication project can inherently have quadratic output; offer a deliberate result cap or grouping mode only if that workload matters.

### D9. Replace repeated subtree strings with compact structural identities

`fingerprints` materializes the full printed text of every subtree. Deep trees avoid Python recursion errors but still retain quadratic amounts of text.

A nested list of the form `[K("node"), child]` produced:

| Depth | Total fingerprint characters | Peak traced allocations |
| ---: | ---: | ---: |
| 500 | 1,004,510 | 1.08 MiB |
| 1,000 | 4,009,010 | 4.00 MiB |
| 2,000 | 16,018,010 | 15.70 MiB |

Evidence: [_printed](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/shape.py#L46) and [fingerprints](https://github.com/bandoyer/dryer/blob/66ff6d21a42c04afcad89c78a80066176d1294b0/src/dryer/shape.py#L98).

Use bottom-up interned identities, or stable digests with a stated collision policy, to represent each subtree once. Preserve the current set-based Jaccard semantics. This is a larger change than the comparison improvements and needs equivalence fixtures.

### D10. Simplify maintenance where there is duplication or hidden state

- Replace the handwritten option loop with a standard parser if its exit codes and help behavior can be preserved. Share behavioral fixtures with crapper and mutator before extracting common CLI code. Their selection rules already differ, so copying one implementation over the others is unsafe.
- Pass source bytes through the normalizer rather than assigning module-global `_DATA`. The current sequential CLI is unaffected; concurrent library use would need isolated state.
- Keep the explicit stack walks. They solve a tested deep-tree problem. Review helper functions that only relay arguments or return constants when touching nearby code; do not inline them merely to hit a line-count target.
- Validate that `--threshold` is finite and between 0 and 1. `--threshold nan` is accepted, and `score < nan` is always false, so every pair passes the threshold check.
- Detect tree-sitter error nodes and report skipped or partial files. Non-Clojure extraction currently returns no warning even when parsing recovers from invalid syntax.

### D11. Establish a small release and ownership process

The tracked tree has no CI workflow or release configuration. Add Linux tests for Python 3.11 and a current supported Python, minimum/current parser compatibility, and a clean wheel-install CLI smoke test. If macOS is supported, exercise the launcher there too.

Keep upstream attribution. Add fork-specific project URLs, supported platforms, release notes, and installation instructions. All three launch scripts consider an existing `.venv/bin/python` proof that installation succeeded; an interrupted first install leaves later runs unable to recover. Check importability or install completion, and make installation failures stop the launcher clearly.

Use atomic replacement for `.metrics/dry.edn` so interruption cannot expose a truncated report. Add an explicit distinction between full and partial reports before treating the file as a durable project-wide snapshot.

## Noted

These properties are useful or intentional, with limits worth preserving.

- No extra runtime service, database, framework, or generated-code directory is present. The direct runtime dependencies are the parser and its language pack. The main bloat is repeated subtree text at runtime, not a large application framework.
- The normalizer and reader use explicit stacks. Existing deep-expression coverage is valuable.
- Ignoring names, literal values, and repetition multiplicity is part of the chosen structural fingerprint metric. A score of `1.0` does not prove semantic equivalence. Fix D1 without turning this into a semantic-equivalence checker.
- `--changed` compares changed files with one another, not against unchanged source. The help states that selection rule. A changed-versus-entire-project mode would be a separate feature.
- `.js` and related JavaScript extensions are not advertised or discovered by dryer, unlike crapper and mutator. Add them only if you want a consistent suite-wide language matrix.
- Test assertions cover renamed locals, changed callees, score ordering, UTF-8 Git paths, and report replacement. The missing tests are specific syntax and lifecycle boundaries, not an absence of useful tests.

## Dismissed

These are not reasons to delay ownership or rewrite the tool.

- A full rewrite, a service layer, or a plugin framework would add maintenance cost without addressing the reproduced defects.
- Constructors, nested callbacks, Clojure platform-branch selection, and Rust `mod tests` omissions are documented scope choices. Expanding them is product work, not automatically a bug fix.
- Small helper functions are not inherently bloat. Preserve helpers that express a real rule or support stack-safe traversal.

## Proposed order

1. Fix D1–D5 and add the corresponding semantic and span fixtures. These determine whether results mean what the README says.
2. Fix D6–D7, installation recovery, and CI. Publish a documented compatibility matrix before a new release.
3. Apply the low-risk comparison improvements in D8 and repeat the same benchmark plus a representative repository scan.
4. Change fingerprint storage only if measured project size justifies D9. Defer broader shared-library extraction until the three tools have stable behavior tests.
