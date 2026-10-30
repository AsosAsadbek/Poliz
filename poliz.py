"""
POLIZ (teskari polyak yozuvi, RPN) mantiqi.

  tokenize()      — ifodani tokenlarga ajratadi va sintaksisini tekshiradi
  to_poliz()      — Shunting-yard (Deykstra) algoritmi, har bir qadam yozib boriladi
  evaluate()      — POLIZ ni stek yordamida hisoblaydi, har bir qadam yozib boriladi
  build_tree()    — POLIZ dan ifoda daraxtini quradi
  calculate()     — hammasini bitta chaqiruvda bajaradi

Qo'llab-quvvatlanadi: butun va kasr sonlar (3.5 yoki 3,5), + - * / ^,
qavslar, unar minus/plyus. Unar minus POLIZ da "~" bilan belgilanadi;
agar u to'g'ridan-to'g'ri songa qo'llansa, manfiy son sifatida yoziladi (-5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

NEG = "~"  # unar minus belgisi

# belgi: (ustuvorlik, o'ngdan assotsiativmi)
OPERATORS = {
    "+": (1, False),
    "-": (1, False),
    "*": (2, False),
    "/": (2, False),
    NEG: (3, True),
    "^": (4, True),
}

OP_NAMES = {
    "+": "qo'shish",
    "-": "ayirish",
    "*": "ko'paytirish",
    "/": "bo'lish",
    "^": "darajaga ko'tarish",
    NEG: "unar minus",
}

# Kiritishda qabul qilinadigan muqobil belgilar
ALIASES = {"×": "*", "·": "*", "÷": "/", ":": "/", "−": "-", "–": "-", "**": "^"}


class PolizError(Exception):
    """Ifodadagi xato. pos — xato joyi (0 dan boshlab), bo'lmasa None."""

    def __init__(self, message: str, pos: int | None = None, length: int = 1):
        super().__init__(message)
        self.message = message
        self.pos = pos
        self.length = length


@dataclass(frozen=True)
class Token:
    kind: str  # "num", "op", "lparen", "rparen"
    text: str  # POLIZ da ko'rinadigan matn
    pos: int  # ifodadagi o'rni
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
    pos: int | None = None  # tokenning ifodadagi o'rni (belgilash uchun)
    length: int = 1


@dataclass
class Node:
    label: str
    children: list["Node"] = field(default_factory=list)


@dataclass
class Result:
    expression: str
    tokens: list[Token]
    poliz: list[Token]
    value: float
    convert_steps: list[Step]
    eval_steps: list[Step]
    tree: Node

    @property
    def poliz_text(self) -> str:
        return " ".join(t.text for t in self.poliz)

    @property
    def value_text(self) -> str:
        return format_number(self.value)


def format_number(x: float) -> str:
    """19.0 -> '19', 0.30000000000000004 -> '0.3', 1e20 -> '1e+20'."""
    if x == 0:
        return "0"  # -0.0 ham
    if math.isfinite(x) and x == int(x) and abs(x) < 1e15:
        return str(int(x))
    return format(x, ".12g")


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
                        raise PolizError("Sonda ikkinchi kasr nuqtasi", i)
                    seen_dot = True
                i += 1
            raw = expr[start:i].replace(",", ".")
            if raw.endswith("."):
                raw = raw[:-1]
            if raw.startswith("."):
                raw = "0" + raw
            tokens.append(Token("num", raw, start, i - start, float(raw)))
            continue

        two = expr[i:i + 2]
        if two in ALIASES:
            tokens.append(Token("op", ALIASES[two], i, 2))
            i += 2
            continue
        sym = ALIASES.get(ch, ch)
        if sym in "+-*/^":
            tokens.append(Token("op", sym, i))
        elif sym in "([{":
            tokens.append(Token("lparen", "(", i))
        elif sym in ")]}":
            tokens.append(Token("rparen", ")", i))
        else:
            raise PolizError(f"Noma'lum belgi: «{ch}»", i)
        i += 1
    return tokens


def tokenize(expr: str) -> list[Token]:
    """Tokenlarga ajratadi, unar minusni ajratib oladi va sintaksisni tekshiradi."""
    raw = _scan(expr)
    if not raw:
        raise PolizError("Ifoda kiritilmagan")

    tokens: list[Token] = []
    expect_operand = True
    depth: list[Token] = []
    i = 0
    while i < len(raw):
        t = raw[i]
        if expect_operand:
            if t.kind == "num":
                tokens.append(t)
                expect_operand = False
            elif t.kind == "lparen":
                tokens.append(t)
                depth.append(t)
            elif t.kind == "op" and t.text in "+-":
                nxt = raw[i + 1] if i + 1 < len(raw) else None
                after = raw[i + 2] if i + 2 < len(raw) else None
                if t.text == "+":
                    pass  # unar plyus hech narsa o'zgartirmaydi
                elif (nxt is not None and nxt.kind == "num"
                      and not (after is not None and after.text == "^")):
                    # -5 -> manfiy son (lekin -2^2 = -(2^2), shuning uchun ^ dan oldin emas)
                    tokens.append(Token("num", "-" + nxt.text, t.pos,
                                        nxt.pos + nxt.length - t.pos, -nxt.value))
                    i += 1
                    expect_operand = False
                else:
                    tokens.append(Token("op", NEG, t.pos))
            elif t.kind == "rparen":
                if tokens and tokens[-1].kind == "lparen":
                    raise PolizError("Qavs ichi bo'sh", tokens[-1].pos, t.pos - tokens[-1].pos + 1)
                raise PolizError("Bu yerda son yoki «(» kutilgan edi", t.pos)
            else:
                raise PolizError(f"«{t.text}» dan oldin son yetishmayapti", t.pos)
        else:
            if t.kind == "op":
                tokens.append(t)
                expect_operand = True
            elif t.kind == "rparen":
                if not depth:
                    raise PolizError("Ochilmagan qavs yopilyapti", t.pos)
                depth.pop()
                tokens.append(t)
            else:
                prev = tokens[-1]
                raise PolizError(
                    f"«{prev.text}» va «{t.text}» orasida amal belgisi yo'q", t.pos)
        i += 1

    if expect_operand:
        last = raw[-1]
        raise PolizError("Ifoda tugallanmagan: oxirida son yetishmayapti",
                         last.pos + last.length - 1)
    if depth:
        raise PolizError("Qavs yopilmagan", depth[-1].pos)
    return tokens


# ---------------------------------------------------------------- Shunting-yard

def to_poliz(tokens: list[Token]) -> tuple[list[Token], list[Step]]:
    """Infiks tokenlarni POLIZ ga o'tkazadi (Deykstraning saralash stansiyasi)."""
    output: list[Token] = []
    stack: list[Token] = []
    steps: list[Step] = []

    def snap(tok: str, action: str, src: Token | None = None) -> None:
        steps.append(Step(tok, action, [s.text for s in stack], [o.text for o in output],
                          src.pos if src else None, src.length if src else 1))

    for t in tokens:
        if t.kind == "num":
            output.append(t)
            snap(t.text, "Son → chiqishga", t)
        elif t.kind == "op":
            prec, right = OPERATORS[t.text]
            popped = []
            if t.text != NEG:  # prefiks amal hech narsani siqib chiqarmaydi
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
                snap(t.text, f"{moved} → chiqishga; «{t.text}» stekka", t)
            else:
                snap(t.text, f"«{t.text}» stekka ({OP_NAMES[t.text]})", t)
        elif t.kind == "lparen":
            stack.append(t)
            snap("(", "Qavs stekka", t)
        else:  # rparen
            popped = []
            while stack[-1].kind != "lparen":
                popped.append(stack.pop())
                output.append(popped[-1])
            stack.pop()
            moved = " ".join(p.text for p in popped)
            snap(")", f"{moved} → chiqishga; qavslar o'chiriladi" if popped
                 else "Juft qavs o'chiriladi", t)

    if stack:
        popped = []
        while stack:
            popped.append(stack.pop())
            output.append(popped[-1])
        snap("—", "Oxiri: " + " ".join(p.text for p in popped) + " → chiqishga")
    return output, steps


# ---------------------------------------------------------------- hisoblash

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
                raise PolizError("Nolga bo'lish mumkin emas", tok.pos)
            r = a / b
        else:  # ^
            if a == 0 and b < 0:
                raise PolizError("Nolni manfiy darajaga ko'tarib bo'lmaydi", tok.pos)
            if a < 0 and b != int(b):
                raise PolizError("Manfiy sonni kasr darajaga ko'tarib bo'lmaydi", tok.pos)
            r = math.pow(a, b)
    except OverflowError:
        raise PolizError("Natija juda katta", tok.pos) from None
    if not math.isfinite(r):
        raise PolizError("Natija juda katta", tok.pos)
    return r


def evaluate(poliz: list[Token]) -> tuple[float, list[Step]]:
    """POLIZ ni chapdan o'ngga o'qib, stek yordamida hisoblaydi."""
    stack: list[float] = []
    steps: list[Step] = []

    def snap(tok: Token, action: str) -> None:
        steps.append(Step(tok.text, action, [format_number(v) for v in stack], [],
                          tok.pos, tok.length))

    for t in poliz:
        if t.kind == "num":
            stack.append(t.value)
            snap(t, "Son stekka")
        elif t.text == NEG:
            a = stack.pop()
            stack.append(-a)
            snap(t, f"−({format_number(a)}) = {format_number(-a)}")
        else:
            b = stack.pop()
            a = stack.pop()
            r = _apply(t.text, a, b, t)
            stack.append(r)
            snap(t, f"{format_number(a)} {t.text} {format_number(b)} = {format_number(r)}")
    return stack[0], steps


def build_tree(poliz: list[Token]) -> Node:
    stack: list[Node] = []
    for t in poliz:
        if t.kind == "num":
            stack.append(Node(t.text))
        elif t.text == NEG:
            stack.append(Node(NEG, [stack.pop()]))
        else:
            b, a = stack.pop(), stack.pop()
            stack.append(Node(t.text, [a, b]))
    return stack[0]


def calculate(expr: str) -> Result:
    tokens = tokenize(expr)
    poliz, convert_steps = to_poliz(tokens)
    value, eval_steps = evaluate(poliz)
    return Result(expr, tokens, poliz, value, convert_steps, eval_steps, build_tree(poliz))
