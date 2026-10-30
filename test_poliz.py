import unittest

from poliz import PolizError, calculate, format_number


class TestPoliz(unittest.TestCase):
    def check(self, expr, poliz, value):
        r = calculate(expr)
        self.assertEqual(r.poliz_text, poliz)
        self.assertAlmostEqual(r.value, value)

    def test_screenshot_example(self):
        self.check("(3 + 4) * 2-(- 5)", "3 4 + 2 * -5 -", 19)

    def test_pdf_numeric_examples(self):
        self.check("(5+3)*2", "5 3 + 2 *", 16)
        self.check("2 + 3 * 4", "2 3 4 * +", 14)
        self.check("(10 + 5) * 2", "10 5 + 2 *", 30)

    def test_pdf_stack_states(self):
        r = calculate("2 + 3 * 4")
        self.assertEqual([s.stack for s in r.eval_steps],
                         [["2"], ["2", "3"], ["2", "3", "4"], ["2", "12"], ["14"]])

    def test_pdf_symbolic_table(self):
        table = {
            "A + B": "A B +",
            "A - B": "A B -",
            "A * B": "A B *",
            "A / B": "A B /",
            "(A+B)*C": "A B + C *",
            "A+B*C": "A B C * +",
            "(A-B)/(C+D)": "A B - C D + /",
            "(A+B)*(C-D)/E": "A B + C D - * E /",
        }
        for infix, poliz in table.items():
            r = calculate(infix)
            self.assertEqual(r.poliz_text, poliz, infix)
            self.assertIsNone(r.value)
            self.assertEqual(r.symbolic, infix.replace(" ", ""))

    def test_symbolic_steps(self):
        r = calculate("(A+B)*(C-D)/E")
        actions = [s.action for s in r.symbolic_steps if "olinadi" in s.action]
        self.assertEqual(actions, [
            "A va B olinadi → A+B",
            "C va D olinadi → C-D",
            "A+B va C-D olinadi → (A+B)*(C-D)",
            "(A+B)*(C-D) va E olinadi → (A+B)*(C-D)/E",
        ])

    def test_symbolic_parentheses_minimal(self):
        self.assertEqual(calculate("A - (B - C)").symbolic, "A-(B-C)")
        self.assertEqual(calculate("(A - B) - C").symbolic, "A-B-C")
        self.assertEqual(calculate("(A ^ B) ^ C").symbolic, "(A^B)^C")
        self.assertEqual(calculate("-(A + B)").symbolic, "-(A+B)")
        self.assertEqual(calculate("(-5) ^ 2").symbolic, "(-5)^2")

    def test_variables_with_values(self):
        r = calculate("(A+B)*(C-D)/E", {"A": 1, "B": 2, "C": "7", "D": "1,5", "E": ""})
        self.assertEqual(r.variables, ["A", "B", "C", "D", "E"])
        self.assertEqual(r.missing, ["E"])
        self.assertIsNone(r.value)
        r = calculate("(A+B)*(C-D)/E", {"A": 1, "B": 2, "C": "7", "D": "1,5", "E": 2})
        self.assertAlmostEqual(r.value, 8.25)
        self.assertEqual(r.missing, [])

    def test_assignment(self):
        r = calculate("x = (a + b) * c;", {"a": 1, "b": 2, "c": 3})
        self.assertEqual(r.poliz_text, "x a b + c * =")
        self.assertEqual(r.symbolic, "x=(a+b)*c")
        self.assertEqual(r.target, "x")
        self.assertEqual(r.variables, ["a", "b", "c"])
        self.assertEqual(r.value, 9)
        self.assertEqual(r.eval_steps[-1].action, "x = 9")
        self.check("y = 2 ^ 3", "y 2 3 ^ =", 8)

    def test_precedence(self):
        self.check("2 + 3 * 4", "2 3 4 * +", 14)
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
        self.assertEqual(calculate("-A * B").poliz_text, "A ~ B *")

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
        self.assertEqual(r.to_dict()["value"], "3")

    def assertError(self, expr, pos, values=None):
        with self.assertRaises(PolizError) as cm:
            calculate(expr, values)
        self.assertEqual(cm.exception.pos, pos, cm.exception.message)

    def test_errors(self):
        self.assertError("", None)
        self.assertError("   ", None)
        self.assertError("2 + $", 4)
        self.assertError("(1 + 2", 0)
        self.assertError("1 + 2)", 5)
        self.assertError("1 +", 2)
        self.assertError("* 2", 0)
        self.assertError("2 (3)", 2)
        self.assertError("2 3", 2)
        self.assertError("2a", 1)
        self.assertError("()", 0)
        self.assertError("1.2.3", 3)
        self.assertError("5 / (2 - 2)", 2)
        self.assertError("(-8) ^ 0.5", 5)
        self.assertError("10 ^ 1000", 3)
        self.assertError("x =", 2)
        self.assertError("a = b = c", 6)
        self.assertError("1 = 2", 2)
        self.assertError("1; 2", 1)
        self.assertError("A / B", 2, {"A": 1, "B": 0})
        self.assertError("A + 1", None, {"A": "abc"})


if __name__ == "__main__":
    unittest.main()
