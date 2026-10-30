import unittest

from poliz import PolizError, calculate, format_number


class TestPoliz(unittest.TestCase):
    def check(self, expr, poliz, value):
        r = calculate(expr)
        self.assertEqual(r.poliz_text, poliz)
        self.assertAlmostEqual(r.value, value)

    def test_screenshot_example(self):
        self.check("(3 + 4) * 2-(- 5)", "3 4 + 2 * -5 -", 19)

    def test_precedence(self):
        self.check("2 + 3 * 4", "2 3 4 * +", 14)
        self.check("(2 + 3) * 4", "2 3 + 4 *", 20)
        self.check("10 - 4 - 3", "10 4 - 3 -", 3)
        self.check("100 / 10 / 5", "100 10 / 5 /", 2)

    def test_power_right_associative(self):
        self.check("2 ^ 3 ^ 2", "2 3 2 ^ ^", 512)
        self.check("2 ** 3", "2 3 ^", 8)

    def test_unary_minus(self):
        self.check("-5 + 3", "-5 3 +", -2)
        self.check("-(3 + 4)", "3 4 + ~", -7)
        self.check("-2 ^ 2", "2 2 ^ ~", -4)
        self.check("2 ^ -1", "2 -1 ^", 0.5)
        self.check("3 * -(2 - 5)", "3 2 5 - ~ *", 9)
        self.check("- -5", "-5 ~", 5)
        self.check("+5 - +2", "5 2 -", 3)

    def test_decimals_and_aliases(self):
        self.check("3,5 * 2", "3.5 2 *", 7)
        self.check(".5 + 1.", "0.5 1 +", 1.5)
        self.check("6 ÷ 3 × 2", "6 3 / 2 *", 4)
        self.check("[1 + 2] * {3}", "1 2 + 3 *", 9)

    def test_formatting(self):
        self.assertEqual(format_number(19.0), "19")
        self.assertEqual(format_number(0.1 + 0.2), "0.3")
        self.assertEqual(format_number(-0.0), "0")
        self.assertEqual(calculate("1/3").value_text, "0.333333333333")

    def test_steps_recorded(self):
        r = calculate("1 + 2")
        self.assertEqual(len(r.convert_steps), 4)  # 1, +, 2, oxiri
        self.assertEqual(r.convert_steps[-1].output, ["1", "2", "+"])
        self.assertEqual(r.eval_steps[-1].stack, ["3"])
        self.assertEqual(r.tree.label, "+")

    def assertError(self, expr, pos):
        with self.assertRaises(PolizError) as cm:
            calculate(expr)
        self.assertEqual(cm.exception.pos, pos, cm.exception.message)

    def test_errors(self):
        self.assertError("", None)
        self.assertError("   ", None)
        self.assertError("2 + a", 4)
        self.assertError("(1 + 2", 0)
        self.assertError("1 + 2)", 5)
        self.assertError("1 +", 2)
        self.assertError("* 2", 0)
        self.assertError("2 (3)", 2)
        self.assertError("2 3", 2)
        self.assertError("()", 0)
        self.assertError("1.2.3", 3)
        self.assertError("5 / (2 - 2)", 2)
        self.assertError("(-8) ^ 0.5", 5)
        self.assertError("10 ^ 1000", 3)


if __name__ == "__main__":
    unittest.main()
