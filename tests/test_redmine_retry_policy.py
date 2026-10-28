"""Isolated retry-policy regression checks without Redmine network access."""
import ast
from pathlib import Path
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "redmine_api.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
GET = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "_get")


class RetryPolicyTests(unittest.TestCase):
    def test_module_is_valid_python(self):
        self.assertIsInstance(TREE, ast.Module)

    def test_retry_limits_are_bounded_and_configurable(self):
        self.assertIn('min(5, int(os.getenv("REDMINE_LIST_RETRIES", "5")))', SOURCE)
        self.assertIn('min(20, int(os.getenv("REDMINE_LIST_CONNECT_TIMEOUT", "8")))', SOURCE)

    def test_only_issues_listing_receives_experiment(self):
        self.assertIn('is_listing = path.lstrip("/") == "issues.json"', SOURCE)
        self.assertIn('if is_listing and tentativas == 3:', SOURCE)
        self.assertIn('if is_listing and timeout == (20, 60):', SOURCE)
        self.assertIn('if is_listing:', SOURCE)
        self.assertIn('espera += random.uniform(0, 0.5)', SOURCE)

    def test_no_hidden_adapter_retries(self):
        self.assertIn("max_retries=0", SOURCE)


if __name__ == "__main__":
    unittest.main()
