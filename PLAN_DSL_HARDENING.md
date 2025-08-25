# DSL Hardening Plan (Issue #54)

Scope
- Implement true short-circuit semantics for `and`/`or` (left-to-right).
- Define and implement None semantics (arithmetic -> None; comparisons -> False except == None).
- Introduce ExpressionError hierarchy and replace ValueError.
- Add resource guards: max expression length and AST depth.
- Refactor comparisons with operator map.
- Optional: restrict `value()` attribute access.

Work plan
1. Tests first: add failing tests that capture the new behaviors.
2. Implement evaluator changes in nav_insights/core/dsl.py.
3. Add new exceptions under nav_insights/core/dsl_errors.py (new file) and import in dsl.
4. Add config constants (length/depth) near evaluator to keep scope local for now.
5. Ensure existing tests still pass; adjust as needed where behavior changes are intentional.
6. Update docs with semantics and limits.

