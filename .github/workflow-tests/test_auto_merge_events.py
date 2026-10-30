"""Evaluate actual merge-job event eligibility without executing workflow code."""

import ast
import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
# Interpreter adapted from venus-os-ci-toolkit/tests/test_metadata_events.py.
def evaluate(expression, context):
    """Interpret the small expression subset used here; reject unknown syntax."""
    expression = expression.removeprefix("${{").removesuffix("}}")

    def value(match):
        values = [context]
        for field in match.group().split("."):
            values = (
                [item for value in values for item in value]
                if field == "*"
                else [v.get(field, "") if isinstance(v, dict) else "" for v in values]
            )
        return repr(values if ".*." in match.group() else values[0])

    expression = re.sub(r"\b(?:github|inputs)(?:\.[\w*-]+)+", value, expression)
    expression = expression.replace("&&", " and ").replace("||", " or ")
    expression = re.sub(r"!(?!=)", " not ", expression)
    expression = re.sub(r"\bnull\b", "None", expression)

    def visit(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, (ast.Dict, ast.List)):
            return ast.literal_eval(node)
        if isinstance(node, ast.BoolOp):
            result = visit(node.values[0])
            for child in node.values[1:]:
                if isinstance(node.op, ast.And):
                    result = visit(child) if result else result
                else:
                    result = result if result else visit(child)
            return result
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not visit(node.operand)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = visit(node.left), visit(node.comparators[0])
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.NotEq):
                return left != right
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [visit(arg) for arg in node.args]
            if node.func.id == "fromJSON" and len(args) == 1:
                return json.loads(args[0])
            if node.func.id == "contains" and len(args) == 2:
                return args[1] in args[0]
            if node.func.id == "format" and len(args) == 2:
                return args[0].format(args[1])
        raise AssertionError(f"Unsupported metadata expression: {expression}")

    return visit(ast.parse("(" + expression.strip() + ")", mode="eval").body)



class AutoMergeEventsTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.load(
            (ROOT / ".github/workflows/auto-merge.yml").read_text(), Loader=yaml.BaseLoader
        )
        self.condition = self.workflow["jobs"]["auto-merge"]["if"]

    def allowed(self, event, actor="4alvit", author="dependabot[bot]", same_repo=True,
                branch="main", has_pr=True):
        data = {"github": {"actor": actor, "repository": "example/repo",
            "event_name": event, "ref": "refs/heads/" + branch,
            "event": {"repository": {"default_branch": "main"}}}}
        if has_pr:
            data["github"]["event"]["pull_request"] = {
                "user": {"login": author},
                "head": {"repo": {"full_name": "example/repo" if same_repo else "other/fork"}},
            }
        return bool(evaluate(self.condition, data))

    def test_dependabot_review_event_is_skipped(self):
        self.assertFalse(self.allowed("pull_request_review", actor="dependabot[bot]"))
        self.assertTrue(self.allowed("pull_request_target", actor="dependabot[bot]"))

    def test_ordinary_review_wakeups_are_preserved(self):
        for actor in ("4alvit", "californiantiramisu", "github-actions[bot]"):
            with self.subTest(actor=actor):
                self.assertTrue(self.allowed("pull_request_review", actor=actor))

    def test_completion_and_schedule_paths_need_default_branch(self):
        for event in ("workflow_run", "status", "check_run", "schedule", "workflow_dispatch"):
            with self.subTest(event=event):
                self.assertTrue(self.allowed(event, has_pr=False))
                self.assertFalse(self.allowed(event, has_pr=False, branch="topic"))

    def test_existing_author_and_repository_boundaries_remain(self):
        for event in ("pull_request_target", "pull_request_review"):
            with self.subTest(event=event):
                self.assertFalse(self.allowed(event, author="untrusted"))
                self.assertFalse(self.allowed(event, same_repo=False))
        self.assertFalse(self.allowed("push"))
        self.assertFalse(self.allowed("pull_request"))

    def test_skipped_events_do_not_have_workflow_level_concurrency(self):
        self.assertNotIn("concurrency", self.workflow)
        self.assertEqual(self.workflow["jobs"]["auto-merge"]["concurrency"]["cancel-in-progress"], "false")
        self.assertEqual(self.workflow["jobs"]["auto-merge"]["secrets"],
                         {"BOT_PAT": "${{ secrets.BOT_PAT }}"})


if __name__ == "__main__":
    unittest.main()
