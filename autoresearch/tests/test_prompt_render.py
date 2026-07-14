import unittest

from util import PIPELINE_DIR  # noqa: F401  (sys.path setup)

from harness.prompt_render import render


class TestPromptRender(unittest.TestCase):
    def test_substitutes_known_placeholders_only(self):
        out = render("a {x} b {unknown} c", x="X")
        self.assertEqual(out, "a X b {unknown} c")

    def test_literal_json_braces_survive(self):
        out = render('{"action": "continue"} uses {x}', x="X")
        self.assertEqual(out, '{"action": "continue"} uses X')

    def test_substituted_content_is_never_rescanned(self):
        # an adversarial persona containing another field's placeholder must
        # not have that field spliced into it
        out = render("P: {persona}\nJ: {jd}",
                      persona="I sneakily contain {jd}", jd="SECRET-JD")
        self.assertEqual(out, "P: I sneakily contain {jd}\nJ: SECRET-JD")


if __name__ == "__main__":
    unittest.main()
