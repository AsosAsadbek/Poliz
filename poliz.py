"""
POLIZ (Polşa invers yozuvi, RPN) mantiqi. Interfeysga bogʼliq emas.

  tokenize()          — ifodani tokenlarga ajratadi va sintaksisini tekşiradi
  to_poliz()          — Shunting-yard (Deykstra) algoritmi, har bir qadam yozib boriladi
  evaluate()          — POLIZni stek yordamida sonlarda hisoblaydi
  evaluate_symbolic() — POLIZni harflarda «hisoblaydi»: A B + → A+B
  build_tree()        — POLIZdan ifoda daraxtini quradi
  calculate()         — hammasini bitta çaqiruvda bajaradi

Qöllab-quvvatlanadi: butun va kasr sonlar (3.5 yoki 3,5), özgaruvçilar (A, x1),
+ - * / ^, qavslar, unar minus/plyus va boşida qiymat beriş: x = (a + b) * c;
Unar minus POLIZda «~» bilan belgilanadi; agar u töğridan-töğri songa qöllansa,
manfiy son sifatida yoziladi (-5).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

NEG = "~"  # unar minus belgisi
ASSIGN = "="

# belgi: (ustuvorlik, öngdan assotsiativmi)
OPERATORS = {
    ASSIGN: (0, True),
    "+": (1, False),
    "-": (1, False),
    "*": (2, False),
    "/": (2, False),
    NEG: (3, True),
    "^": (4, True),
}

OP_NAMES = {
    "+": "qöşiş",
    "-": "ayiriş",
    "*": "köpaytiriş",
    "/": "böliş",
    "^": "darajaga kötariş",
    NEG: "unar minus",
    ASSIGN: "qiymat beriş",
}

# Kiritişda qabul qilinadigan muqobil belgilar
ALIASES = {"×": "*", "·": "*", "÷": "/", ":": "/", "−": "-", "–": "-", "**": "^"}

ATOM = 9  # son yoki özgaruvçining «ustuvorligi» (qavs talab qilmaydi)


class PolizError(Exception):
    """Ifodadagi xato. pos — xato joyi (0 dan boşlab), bölmasa None."""

    def __init__(self, message: str, pos: int | None = None, length: int = 1):
        super().__init__(message)
        self.message = message
        self.pos = pos
        self.length = length


@dataclass(frozen=True)
class Token:
    kind: str  # "num", "var", "target", "op", "lparen", "rparen"
    text: str  # POLIZda körinadigan matn
    pos: int  # ifodadagi örni
    length: int = 1
    value: float | None = None

    def __str__(self) -> str:
        return self.text


@dataclass
class Step:
    token: str
    action: str
    stack: list[str]
    output: list[str]
    pos: int | None = None  # tokenning ifodadagi örni (belgilaş uçun)
    length: int = 1


@dataclass
class Node:
    label: str
    kind: str  # "op", "num", "var"
    children: list["Node"] = field(default_factory=list)


@dataclass
class Result:
    expression: str
    tokens: list[Token]
    poliz: list[Token]
    convert_steps: list[Step]
    symbolic: str  # POLIZdan qayta tiklangan infiks ifoda
    symbolic_steps: list[Step]
    variables: list[str]  # qiymati kerak bölgan özgaruvçilar
    missing: list[str]  # qiymati berilmaganlari
    target: str | None  # x = ... dagi x
    value: float | None  # missing bölsa None
    eval_steps: list[Step]  # sonli hisoblaş qadamlari (value None bölsa — böş)
    tree: Node

    @property
    def poliz_text(self) -> str:
        return " ".join(t.text for t in self.poliz)

    @property
    def value_text(self) -> str:
        return "" if self.value is None else format_number(self.value)

    def to_dict(self) -> dict:
        """Interfeysga (JSON) yuboriş uçun."""
        return {
            "expression": self.expression,
            "poliz": [{"text": t.text, "kind": t.kind, "pos": t.pos, "length": t.length}
                      for t in self.poliz],
            "poliz_text": self.poliz_text,
            "convert_steps": [asdict(s) for s in self.convert_steps],
            "symbolic": self.symbolic,
            "symbolic_steps": [asdict(s) for s in self.symbolic_steps],
            "variables": self.variables,
            "missing": self.missing,
            "target": self.target,
            "value": self.value_text or None,
            "eval_steps": [asdict(s) for s in self.eval_steps],
            "tree": asdict(self.tree),
        }


def format_number(x: float) -> str:
    """19.0 -> '19', 0.30000000000000004 -> '0.3', 1e20 -> '1e+20'."""
    if x == 0:
        return "0"  # -0.0 ham
    if math.isfinite(x) and x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return format(x, ".12g")


def parse_number(text: str) -> float:
    return float(text.strip().replace(",", ".").replace("−", "-"))


# ---------------------------------------------------------------- tokenlar

def _scan(expr: str) -> list[Token]:
    """Ifodani xom tokenlarga ajratadi (unar/binar farqlanmaydi)."""
    tokens: list[Token] = []
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue

        if ch.isdigit() or (ch in ".," and i + 1 < n and expr[i + 1].isdigit()):
            start = i
            seen_dot = False
            while i < n and (expr[i].isdigit() or expr[i] in ".,"):
                if expr[i] in ".,":
                    if seen_dot:
                        raise PolizError("Sonda ikkinçi kasr nuqtasi", i)
                    seen_dot = True
                i += 1
            raw = expr[start:i].replace(",", ".")
            if raw.endswith("."):
                raw = raw[:-1]
            if raw.startswith("."):
                raw = "0" + raw
            tokens.append(Token("num", raw, start, i - start, float(raw)))
            continue

        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (expr[i].isalnum() or expr[i] == "_"):
                i += 1
            tokens.append(Token("var", expr[start:i], start, i - start))
            continue

        if ch == ";":
            if expr[i + 1:].strip():
                raise PolizError("«;» faqat ifoda oxirida kelişi mumkin", i)
            break

        two = expr[i:i + 2]
        if two in ALIASES:
            tokens.append(Token("op", ALIASES[two], i, 2))
            i += 2
            continue
        sym = ALIASES.get(ch, ch)
        if sym in "+-*/^=":
            tokens.append(Token("op", sym, i))
        elif sym in "([{":
            tokens.append(Token("lparen", "(", i))
        elif sym in ")]}":
            tokens.append(Token("rparen", ")", i))
        else:
            raise PolizError(f"Nomaʼlum belgi: «{ch}»", i)
        i += 1
    return tokens


def tokenize(expr: str) -> list[Token]:
    """Tokenlarga ajratadi, unar minusni ajratib oladi va sintaksisni tekşiradi."""
    raw = _scan(expr)
    if not raw:
        raise PolizError("Ifoda kiritilmagan")

    tokens: list[Token] = []
    # x = ... : qiymat beriş faqat boşida, özgaruvçidan keyin
    if len(raw) >= 2 and raw[0].kind == "var" and raw[1].text == ASSIGN:
        t = raw[0]
        tokens += [Token("target", t.text, t.pos, t.length), raw[1]]
        raw = raw[2:]
        if not raw:
            raise PolizError("«=» dan keyin ifoda yetişmayapti", tokens[-1].pos)

    expect_operand = True
    depth: list[Token] = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if t.text == ASSIGN:
            raise PolizError("«=» faqat boşida özgaruvçidan keyin kelişi mumkin: x = …", t.pos)
        if expect_operand:
            if t.kind in ("num", "var"):
                tokens.append(t)
                expect_operand = False
            elif t.kind == "lparen":
                tokens.append(t)
                depth.append(t)
            elif t.kind == "op" and t.text in "+-":
                nxt = raw[i + 1] if i + 1 < len(raw) else None
                after = raw[i + 2] if i + 2 < len(raw) else None
                if t.text == "+":
                    pass  # unar plyus heç narsa özgartirmaydi
                elif (nxt is not None and nxt.kind == "num"
                      and not (after is not None and after.text == "^")):
                    # -5 -> manfiy son (lekin -2^2 = -(2^2), şuning uçun ^ dan oldin emas)
                    tokens.append(Token("num", "-" + nxt.text, t.pos,
                                        nxt.pos + nxt.length - t.pos, -nxt.value))
                    i += 1
                    expect_operand = False
                else:
                    tokens.append(Token("op", NEG, t.pos))
            elif t.kind == "rparen":
                if tokens and tokens[-1].kind == "lparen":
                    raise PolizError("Qavs içi böş", tokens[-1].pos, t.pos - tokens[-1].pos + 1)
                raise PolizError("Bu yerda operand yoki «(» kutilgan edi", t.pos)
            else:
                raise PolizError(f"«{t.text}» dan oldin operand yetişmayapti", t.pos)
        else:
            if t.kind == "op":
                tokens.append(t)
                expect_operand = True
            elif t.kind == "rparen":
                if not depth:
                    raise PolizError("Oçilmagan qavs yopilyapti", t.pos)
                depth.pop()
                tokens.append(t)
            else:
                prev = tokens[-1]
                raise PolizError(
                    f"«{prev.text}» va «{t.text}» orasida amal belgisi yöq", t.pos, t.length)
        i += 1

    if expect_operand:
        last = raw[-1]
        raise PolizError("Ifoda tugallanmagan: oxirida operand yetişmayapti",
                         last.pos + last.length - 1)
    if depth:
        raise PolizError("Qavs yopilmagan", depth[-1].pos)
    return tokens


# ---------------------------------------------------------------- Shunting-yard

def to_poliz(tokens: list[Token]) -> tuple[list[Token], list[Step]]:
    """Infiks tokenlarni POLIZga ötkazadi (Deykstraning «saralaş stansiyasi»)."""
    output: list[Token] = []
    stack: list[Token] = []
    steps: list[Step] = []

    def snap(tok: str, action: str, src: Token | None = None) -> None:
        steps.append(Step(tok, action, [s.text for s in stack], [o.text for o in output],
                          src.pos if src else None, src.length if src else 1))

    for t in tokens:
        if t.kind == "target":
            output.append(t)
            snap(t.text, "Natija yoziladigan özgaruvçi → çiqişga", t)
        elif t.kind in ("num", "var"):
            output.append(t)
            snap(t.text, "Operand → çiqişga", t)
        elif t.kind == "op":
            prec, right = OPERATORS[t.text]
            popped = []
            if t.text != NEG:  # prefiks amal heç narsani siqib çiqarmaydi
                while stack and stack[-1].kind == "op":
                    top_prec = OPERATORS[stack[-1].text][0]
                    if top_prec > prec or (top_prec == prec and not right):
                        popped.append(stack.pop())
                        output.append(popped[-1])
                    else:
                        break
            stack.append(t)
            if popped:
                moved = " ".join(p.text for p in popped)
                snap(t.text, f"{moved} → çiqişga; «{t.text}» stekka", t)
            else:
                snap(t.text, f"«{t.text}» stekka ({OP_NAMES[t.text]})", t)
        elif t.kind == "lparen":
            stack.append(t)
            snap("(", "«(» stekka", t)
        else:  # rparen
            popped = []
            while stack[-1].kind != "lparen":
                popped.append(stack.pop())
                output.append(popped[-1])
            stack.pop()
            moved = " ".join(p.text for p in popped)
            snap(")", f"{moved} → çiqişga; qavslar taşlanadi" if popped
                 else "Juft qavs taşlanadi", t)

    if stack:
        popped = []
        while stack:
            popped.append(stack.pop())
            output.append(popped[-1])
        snap("—", "Oxiri: " + " ".join(p.text for p in popped) + " → çiqişga")
    return output, steps


# ---------------------------------------------------------------- hisoblaş

def _apply(op: str, a: float, b: float, tok: Token) -> float:
    try:
        if op == "+":
            r = a + b
        elif op == "-":
            r = a - b
        elif op == "*":
            r = a * b
        elif op == "/":
            if b == 0:
                raise PolizError("Nolga böliş mumkin emas", tok.pos)
            r = a / b
        else:  # ^
            if a == 0 and b < 0:
                raise PolizError("Nolni manfiy darajaga kötarib bölmaydi", tok.pos)
            if a < 0 and b != int(b):
                raise PolizError("Manfiy sonni kasr darajaga kötarib bölmaydi", tok.pos)
            r = math.pow(a, b)
    except OverflowError:
        raise PolizError("Natija juda katta", tok.pos) from None
    if not math.isfinite(r):
        raise PolizError("Natija juda katta", tok.pos)
    return r


def evaluate(poliz: list[Token], values: dict[str, float] | None = None
             ) -> tuple[float, list[Step]]:
    """POLIZni çapdan öngga öqib, stek yordamida hisoblaydi."""
    values = values or {}
    stack: list[float] = []
    steps: list[Step] = []
    target: Token | None = None
    f = format_number

    def snap(tok: Token, action: str) -> None:
        steps.append(Step(tok.text, action, [f(v) for v in stack], [], tok.pos, tok.length))

    for t in poliz:
        if t.kind == "target":
            target = t
            steps.append(Step(t.text, "Natija şu özgaruvçiga yoziladi", [], [], t.pos, t.length))
        elif t.kind == "num":
            stack.append(t.value)
            snap(t, "stekka joylanadi")
        elif t.kind == "var":
            stack.append(values[t.text])
            snap(t, f"{t.text} = {f(values[t.text])} → stekka joylanadi")
        elif t.text == NEG:
            a = stack.pop()
            stack.append(-a)
            snap(t, f"{f(a)} olinadi → −({f(a)}) = {f(-a)}, stekka qaytariladi")
        elif t.text == ASSIGN:
            snap(t, f"{target.text} = {f(stack[-1])}")
        else:
            b = stack.pop()
            a = stack.pop()
            r = _apply(t.text, a, b, t)
            stack.append(r)
            snap(t, f"{f(a)} va {f(b)} olinadi → {f(a)}{t.text}{f(b)} = {f(r)}, "
                    "stekka qaytariladi")
    return stack[0], steps


def _wrap(item: tuple[str, int], need: bool) -> str:
    return f"({item[0]})" if need else item[0]


def evaluate_symbolic(poliz: list[Token]) -> tuple[str, list[Step]]:
    """POLIZni harflarda bajaradi: A B + → A+B. Ortiqça qavslar qöyilmaydi."""
    stack: list[tuple[str, int]] = []  # (matn, ustuvorlik)
    steps: list[Step] = []
    target: Token | None = None

    def snap(tok: Token, action: str) -> None:
        steps.append(Step(tok.text, action, [s for s, _ in stack], [], tok.pos, tok.length))

    for t in poliz:
        if t.kind == "target":
            target = t
            steps.append(Step(t.text, "Natija şu özgaruvçiga yoziladi", [], [], t.pos, t.length))
        elif t.kind in ("num", "var"):
            # manfiy son -5 darajada qavs talab qiladi: (-5)^2
            stack.append((t.text, OPERATORS[NEG][0] if t.text.startswith("-") else ATOM))
            snap(t, "stekka joylanadi")
        elif t.text == NEG:
            a = stack.pop()
            r = "-" + _wrap(a, a[1] < OPERATORS[NEG][0])
            stack.append((r, OPERATORS[NEG][0]))
            snap(t, f"{a[0]} olinadi → {r}")
        elif t.text == ASSIGN:
            snap(t, f"{target.text} = {stack[-1][0]}")
        else:
            prec, right = OPERATORS[t.text]
            b, a = stack.pop(), stack.pop()
            left = _wrap(a, a[1] < prec or (a[1] == prec and right))
            rt = _wrap(b, b[1] < prec or (b[1] == prec and not right))
            r = f"{left}{t.text}{rt}"
            stack.append((r, prec))
            snap(t, f"{a[0]} va {b[0]} olinadi → {r}")
    text = stack[0][0]
    return (f"{target.text}={text}" if target else text), steps


def build_tree(poliz: list[Token]) -> Node:
    stack: list[Node] = []
    for t in poliz:
        if t.kind in ("num", "var", "target"):
            stack.append(Node(t.text, "num" if t.kind == "num" else "var"))
        elif t.text == NEG:
            stack.append(Node(NEG, "op", [stack.pop()]))
        else:
            b, a = stack.pop(), stack.pop()
            stack.append(Node(t.text, "op", [a, b]))
    return stack[0]


def calculate(expr: str, values: dict[str, float | str] | None = None) -> Result:
    """Ifodani POLIZga ötkazadi va hisoblaydi.

    values — özgaruvçilar qiymati ({"A": 5} yoki {"A": "5,5"}). Qiymati berilmagan
    özgaruvçi bölsa, ifoda faqat harflarda «hisoblanadi» (value = None).
    """
    tokens = tokenize(expr)
    poliz, convert_steps = to_poliz(tokens)
    symbolic, symbolic_steps = evaluate_symbolic(poliz)

    variables = list(dict.fromkeys(t.text for t in tokens if t.kind == "var"))
    numbers: dict[str, float] = {}
    for name in variables:
        raw = (values or {}).get(name)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        try:
            numbers[name] = parse_number(raw) if isinstance(raw, str) else float(raw)
        except ValueError:
            raise PolizError(f"«{name}» qiymati son emas: «{raw}»") from None
    missing = [v for v in variables if v not in numbers]

    value, eval_steps = (None, []) if missing else evaluate(poliz, numbers)
    target = tokens[0].text if tokens[0].kind == "target" else None
    return Result(expr, tokens, poliz, convert_steps, symbolic, symbolic_steps,
                  variables, missing, target, value, eval_steps, build_tree(poliz))
