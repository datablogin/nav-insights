from __future__ import annotations
from typing import Any, Dict, List
import ast
from functools import lru_cache
import yaml
from jinja2 import Template
from .dsl import eval_expr, value
from .actions import Action, ActionImpact


def _render(template_str: str, ctx: Dict[str, Any]) -> str:
    def pct(x):
        try:
            return f"{float(x) * 100:.0f}%"
        except Exception:
            return "n/a"

    def usd(x):
        try:
            return f"${float(x):,.0f}"
        except Exception:
            return "n/a"

    def value_fn(path: str, default=None):
        return value(path, ctx["root"], default)

    env = {"pct": pct, "usd": usd, "value": value_fn, "action": ctx.get("action", {})}
    return Template(template_str).render(**env)


def _eval_value_or_expr(node: Any, root: Any):
    if isinstance(node, (int, float, bool)) or node is None:
        return node
    if isinstance(node, dict):
        return {k: _eval_value_or_expr(v, root) for k, v in node.items()}
    if isinstance(node, str):
        try:
            return eval_expr(node, root)
        except Exception:
            return node
    if isinstance(node, list):
        return [_eval_value_or_expr(v, root) for v in node]
    return node


def _validate_ruleset(rules: List[Dict[str, Any]]) -> None:
    """Basic structural validation + expression syntax checks at load time."""
    if not isinstance(rules, list):
        raise ValueError("Rules file must parse to a list")
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            raise ValueError(f"Rule #{i} is not a mapping")
        if not r.get("id"):
            raise ValueError(f"Rule #{i} missing 'id'")
        conds = r.get("if_all", [])
        if not isinstance(conds, list):
            raise ValueError(f"Rule {r.get('id')} 'if_all' must be a list")
        for c in conds:
            if not isinstance(c, dict) or "expr" not in c or not isinstance(c["expr"], str):
                raise ValueError(f"Rule {r.get('id')} has invalid condition: {c}")
            # Syntax check only (no evaluation)
            ast.parse(c["expr"], mode="eval")

        # Optional: pre-validate expected_impact expression syntax (best-effort)
        def _walk(node: Any):
            if isinstance(node, dict):
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)
            elif isinstance(node, str):
                try:
                    ast.parse(node, mode="eval")
                except Exception:
                    pass

        _walk(r.get("expected_impact", {}))


@lru_cache(maxsize=32)
def _load_rules_cached(rules_path: str) -> List[Dict[str, Any]]:
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = yaml.safe_load(f) or []
    _validate_ruleset(rules)
    return rules


def clear_rule_cache() -> None:
    _load_rules_cached.cache_clear()


def evaluate_rules(ir: Any, rules_path: str) -> List[Action]:
    rules = _load_rules_cached(rules_path)

    actions: List[Action] = []
    for r in rules:
        conds = r.get("if_all", [])
        if not all(bool(eval_expr(c["expr"], ir)) for c in conds):
            continue

        action_def = r.get("action", {})
        action = {
            "id": f"{r.get('id')}_ACT_{len(actions) + 1}",
            "type": action_def.get("type", "other"),
            "target": action_def.get("target", ""),
            "params": action_def.get("params", {}),
            "priority": r.get("priority", 3),
            "confidence": 0.9,
            "source_rule_id": r.get("id"),
        }
        ctx = {"root": ir, "action": action}
        just_tpl = r.get("justification_template", "")
        justification = _render(just_tpl, ctx) if just_tpl else r.get("description", "")
        exp_imp_raw = r.get("expected_impact", {})
        exp_imp = _eval_value_or_expr(exp_imp_raw, ir)
        impact = None
        if exp_imp:
            impact = ActionImpact(**exp_imp)

        actions.append(
            Action(
                justification=justification.strip(),
                expected_impact=impact,
                **action,
            )
        )
    return actions
