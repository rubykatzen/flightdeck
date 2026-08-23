import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "render.py"
SPEC = importlib.util.spec_from_file_location("render", MODULE_PATH)
render = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render)


class RenderTemplateTest(unittest.TestCase):
    def test_substitutes_braced_var(self):
        result = render.render_template("email: ${ADMIN_MAIL}", {"ADMIN_MAIL": "a@example.com"})
        self.assertEqual(result, "email: a@example.com")

    def test_substitutes_bare_var(self):
        result = render.render_template("email: $ADMIN_MAIL", {"ADMIN_MAIL": "a@example.com"})
        self.assertEqual(result, "email: a@example.com")

    def test_missing_var_becomes_empty_string(self):
        result = render.render_template("email: ${ADMIN_MAIL}", {})
        self.assertEqual(result, "email: ")

    def test_leaves_bash_default_syntax_untouched(self):
        text = "email: ${ADMIN_MAIL:-fallback@example.com}"
        result = render.render_template(text, {"ADMIN_MAIL": "a@example.com"})
        self.assertEqual(result, text)

    def test_leaves_double_dollar_untouched(self):
        result = render.render_template("price: $$5", {})
        self.assertEqual(result, "price: $$5")

    def test_substitutes_multiple_occurrences(self):
        result = render.render_template("${A}-${A}-${B}", {"A": "x", "B": "y"})
        self.assertEqual(result, "x-x-y")


if __name__ == "__main__":
    unittest.main()
