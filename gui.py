"""
POLIZ Kalkulyatori — Tkinter interfeysi.

Klaviatura:
  Enter            hisoblash
  Esc              tozalash
  ↑ / ↓            tarixdagi ifodalar
  Ctrl+Shift+C     natijani nusxalash
  Ctrl+T           yorug' / tungi mavzu
  F1               qo'llanma
"""

from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

from poliz import NEG, OPERATORS, PolizError, Result, calculate

APP_TITLE = "POLIZ Kalkulyatori"
HISTORY_FILE = Path.home() / ".poliz_tarix.json"
HISTORY_LIMIT = 100
LIVE_DELAY_MS = 250

EXAMPLES = [
    "(3 + 4) * 2 - (-5)",
    "2 ^ 3 ^ 2",
    "-(5 - 8) * 4 / 2",
    "3,5 * (2 + 1,5)",
    "((1 + 2) * (3 + 4)) / 7",
]

THEMES = {
    "light": {
        "bg": "#F3F5F9",
        "card": "#FFFFFF",
        "border": "#DDE2EA",
        "text": "#1F2937",
        "muted": "#6B7280",
        "accent": "#2563EB",
        "accent_hover": "#1D4ED8",
        "accent_soft": "#E0EAFF",
        "accent_text": "#FFFFFF",
        "key": "#EEF1F6",
        "key_hover": "#E1E6EE",
        "key_op": "#E0EAFF",
        "key_op_text": "#1D4ED8",
        "success": "#15803D",
        "error": "#DC2626",
        "error_soft": "#FDE2E2",
        "num_chip": "#EEF1F6",
        "op_chip": "#DBE7FF",
        "row_alt": "#F7F9FC",
        "select": "#CFE0FF",
        "tree_line": "#A7B1C2",
    },
    "dark": {
        "bg": "#111827",
        "card": "#1B2433",
        "border": "#2C3647",
        "text": "#E5E7EB",
        "muted": "#9CA3AF",
        "accent": "#3B82F6",
        "accent_hover": "#2563EB",
        "accent_soft": "#1E3A66",
        "accent_text": "#FFFFFF",
        "key": "#253043",
        "key_hover": "#2F3C53",
        "key_op": "#1E3A66",
        "key_op_text": "#BFD4FF",
        "success": "#4ADE80",
        "error": "#F87171",
        "error_soft": "#4A1F24",
        "num_chip": "#2A3547",
        "op_chip": "#1E3A66",
        "row_alt": "#202B3C",
        "select": "#2B4A7A",
        "tree_line": "#4B5563",
    },
}

HELP_TEXT = f"""\
# POLIZ (teskari polyak yozuvi) nima?
Oddiy yozuvda amal sonlar orasida turadi: 3 + 4. POLIZ da esa amal sonlardan \
keyin yoziladi: 3 4 +. Bunday yozuvda qavslar kerak bo'lmaydi va ifodani \
stek yordamida chapdan o'ngga bir marta o'qib hisoblash mumkin.

# 1-bosqich. Ifodani POLIZ ga o'tkazish (Deykstra, «saralash stansiyasi»)
  • Son kelsa — darhol chiqishga yoziladi.
  • Amal kelsa — stek tepasidagi ustuvorligi yuqoriroq (yoki teng va chapdan \
assotsiativ) amallar chiqishga o'tkaziladi, so'ng yangi amal stekka qo'yiladi.
  • «(» stekka qo'yiladi; «)» kelsa — «(» gacha bo'lgan amallar chiqishga \
o'tkaziladi, qavslar tashlab yuboriladi.
  • Ifoda tugagach, stekda qolgan amallar chiqishga o'tkaziladi.

# 2-bosqich. POLIZ ni hisoblash
  • Son — stekka qo'yiladi.
  • Amal — stekdan ikki son olinadi, natija stekka qaytariladi.
  • Oxirida stekda qolgan yagona son — javob.

# Amallar va ustuvorlik
  ^        darajaga ko'tarish   (eng yuqori, o'ngdan: 2^3^2 = 2^9)
  {NEG}        unar minus          (masalan -(3+4) → 3 4 + {NEG})
  *  /     ko'paytirish, bo'lish
  +  -     qo'shish, ayirish   (eng past)

# Kiritish
  • Kasr sonlar: 3.5 yoki 3,5
  • Muqobil belgilar: × · → *,  ÷ : → /,  ** → ^,  [ ] {{ }} → qavs
  • Manfiy son: -5 yoki (-5); POLIZ da -5 ko'rinishida yoziladi

# Klaviatura
  Enter — hisoblash        Esc — tozalash
  ↑ / ↓ — tarixdagi ifodalar
  Ctrl+Shift+C — natijani nusxalash
  Ctrl+T — yorug' / tungi mavzu      F1 — shu qo'llanma

Jadvallardagi qatorni tanlasangiz, mos belgi ifodada ajratib ko'rsatiladi.
"""


def pick_font(root: tk.Misc, candidates: list[str], fallback: str) -> str:
    available = set(tkfont.families(root))
    for name in candidates:
        if name in available:
            return name
    return fallback


class Tooltip:
    """Sichqoncha ustida turganda chiqadigan kichik izoh."""

    def __init__(self, widget: tk.Widget, text: str, app: "App"):
        self.widget, self.text, self.app = widget, text, app
        self.tip: tk.Toplevel | None = None
        self.job: str | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _e=None):
        self._cancel()
        self.job = self.widget.after(500, self._show)

    def _cancel(self):
        if self.job:
            self.widget.after_cancel(self.job)
            self.job = None

    def _show(self):
        if self.tip or not self.widget.winfo_exists():
            return
        c = self.app.c
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg=c["text"], fg=c["card"],
                 font=self.app.f_small, padx=8, pady=4).pack()

    def _hide(self, _e=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


class FlatButton(tk.Button):
    """Tekis, hover effektli, klaviaturadan ham bosiladigan tugma."""

    def __init__(self, master, app: "App", text: str, command, kind: str = "key",
                 font=None, tooltip: str | None = None, **kw):
        c = app.c
        palette = {
            "primary": (c["accent"], c["accent_hover"], c["accent_text"]),
            "key": (c["key"], c["key_hover"], c["text"]),
            "op": (c["key_op"], c["key_hover"], c["key_op_text"]),
            "ghost": (c["card"], c["key"], c["muted"]),
        }
        self._bg, self._hover, fg = palette[kind]
        super().__init__(
            master, text=text, command=command, bg=self._bg, fg=fg,
            activebackground=self._hover, activeforeground=fg,
            relief="flat", bd=0, highlightthickness=2,
            highlightbackground=master["bg"], highlightcolor=c["accent"],
            cursor="hand2", font=font or app.f_body, **{"takefocus": True, **kw})
        self.bind("<Enter>", lambda _e: self.configure(bg=self._hover), add="+")
        self.bind("<Leave>", lambda _e: self.configure(bg=self._bg), add="+")
        self.bind("<Return>", lambda _e: (self.invoke(), "break")[1])
        self.bind("<space>", lambda _e: (self.invoke(), "break")[1])
        if tooltip:
            Tooltip(self, tooltip, app)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = "light"
        self.history: list[dict] = self._load_history()
        self.history_index: int | None = None
        self.result: Result | None = None
        self.live_job: str | None = None
        self.toast_job: str | None = None

        root.title(APP_TITLE)
        root.minsize(940, 640)
        self._center(1180, 760)

        sans = pick_font(root, ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter",
                                "Ubuntu", "Noto Sans", "DejaVu Sans"], "TkDefaultFont")
        mono = pick_font(root, ["Cascadia Mono", "Consolas", "SF Mono", "Menlo",
                                "JetBrains Mono", "Ubuntu Mono", "DejaVu Sans Mono"],
                         "TkFixedFont")
        self.f_title = (sans, 18, "bold")
        self.f_h2 = (sans, 11, "bold")
        self.f_body = (sans, 11)
        self.f_small = (sans, 9)
        self.f_key = (sans, 13)
        self.f_input = (mono, 15)
        self.f_mono = (mono, 11)
        self.f_result = (sans, 26, "bold")

        self._bind_shortcuts()
        self.build()

    # ------------------------------------------------------------ umumiy

    @property
    def c(self) -> dict:
        return THEMES[self.theme]

    def _center(self, w: int, h: int):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = min(w, sw - 40), min(h, sh - 80)
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")

    def _bind_shortcuts(self):
        r = self.root
        r.bind("<Escape>", lambda _e: self.clear())
        r.bind("<F1>", lambda _e: self.show_help())
        r.bind("<Control-t>", lambda _e: self.toggle_theme())
        r.bind("<Control-T>", lambda _e: self.toggle_theme())
        r.bind("<Control-Shift-C>", lambda _e: self.copy(self.result.value_text if self.result else ""))
        r.bind("<Control-l>", lambda _e: self.focus_input())

    def card(self, master, **grid) -> tk.Frame:
        outer = tk.Frame(master, bg=self.c["border"])
        inner = tk.Frame(outer, bg=self.c["card"], padx=18, pady=16)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        outer.grid(**grid)
        return inner

    def label(self, master, text="", style="body", **kw) -> tk.Label:
        fonts = {"body": self.f_body, "h2": self.f_h2, "small": self.f_small,
                 "title": self.f_title, "result": self.f_result, "mono": self.f_mono}
        kw.setdefault("fg", self.c["muted"] if style == "small" else self.c["text"])
        return tk.Label(master, text=text, font=fonts[style], bg=master["bg"],
                        anchor="w", justify="left", **kw)

    # ------------------------------------------------------------ qurish

    def build(self):
        """Butun oynani (qayta) quradi. Mavzu almashganda ham chaqiriladi."""
        c = self.c
        saved_expr = self.get_expr() if hasattr(self, "entry") else ""
        saved_tab = self.tabs.index("current") if hasattr(self, "tabs") else 0
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=c["bg"])
        self._style_ttk()

        main = tk.Frame(self.root, bg=c["bg"], padx=20, pady=14)
        main.pack(fill="both", expand=True)
        self.main_frame = main
        main.columnconfigure(0, weight=0, minsize=410)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        self._build_header(main)
        left = tk.Frame(main, bg=c["bg"])
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        left.columnconfigure(0, weight=1)
        self._build_display(left)
        self._build_keypad(left)
        self._build_tabs(main)
        self._build_statusbar()

        self.tabs.select(saved_tab)
        if saved_expr:
            self.entry.insert("1.0", saved_expr)
        self.render_history()
        if self.result and saved_expr == self.result.expression:
            self.show_result(self.result)
        else:
            self.show_placeholder()
        self.focus_input()

    def _style_ttk(self):
        c = self.c
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("TNotebook", background=c["bg"], borderwidth=1, tabmargins=(0, 0, 0, 0),
                    bordercolor=c["border"], lightcolor=c["card"], darkcolor=c["card"])
        s.configure("TNotebook.Tab", background=c["bg"], foreground=c["muted"],
                    padding=(16, 8), font=self.f_body, borderwidth=1,
                    bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"])
        s.map("TNotebook.Tab",
              background=[("selected", c["card"]), ("active", c["key"])],
              foreground=[("selected", c["accent"]), ("active", c["text"])],
              lightcolor=[("selected", c["card"])], darkcolor=[("selected", c["card"])],
              expand=[("selected", (0, 0, 0, 0))])
        s.configure("Treeview", background=c["card"], fieldbackground=c["card"],
                    foreground=c["text"], rowheight=30, font=self.f_body, borderwidth=0)
        s.map("Treeview", background=[("selected", c["select"])],
              foreground=[("selected", c["text"])])
        s.configure("Treeview.Heading", background=c["key"], foreground=c["muted"],
                    font=self.f_h2, relief="flat", padding=(8, 6))
        s.map("Treeview.Heading", background=[("active", c["key_hover"])])
        s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar", background=c["key"], troughcolor=c["card"],
                        bordercolor=c["card"], arrowcolor=c["muted"], lightcolor=c["key"],
                        darkcolor=c["key"], gripcount=0)
            s.map(f"{orient}.TScrollbar", background=[("active", c["key_hover"])])

    def _build_header(self, main):
        c = self.c
        head = tk.Frame(main, bg=c["bg"])
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        head.columnconfigure(0, weight=1)
        titles = tk.Frame(head, bg=c["bg"])
        titles.grid(row=0, column=0, sticky="w")
        self.label(titles, "POLIZ Kalkulyatori", "title").pack(anchor="w")
        self.label(titles, "Ifodani teskari polyak yozuviga o'tkazish va stek yordamida "
                           "hisoblash", "small").pack(anchor="w")
        actions = tk.Frame(head, bg=c["bg"])
        actions.grid(row=0, column=1, sticky="e")
        theme_text = "☾  Tungi" if self.theme == "light" else "☀  Yorug'"
        FlatButton(actions, self, theme_text, self.toggle_theme, "key", self.f_body,
                   "Mavzuni almashtirish (Ctrl+T)", padx=14, pady=6).pack(side="left", padx=4)
        FlatButton(actions, self, "?  Qo'llanma", self.show_help, "key", self.f_body,
                   "POLIZ qanday ishlaydi (F1)", padx=14, pady=6).pack(side="left", padx=4)

    def _build_display(self, left):
        """Yuqori karta: ifoda, holat qatori, POLIZ va natija — ko'z bir joyda harakatlanadi."""
        c = self.c
        box = self.card(left, row=0, column=0, sticky="ew")
        top = tk.Frame(box, bg=c["card"])
        top.pack(fill="x")
        self.label(top, "Ifodani kiriting", "h2").pack(side="left")

        examples = tk.Menubutton(top, text="Namunalar  ▾", font=self.f_small, bg=c["card"],
                                 fg=c["accent"], activebackground=c["key"],
                                 activeforeground=c["accent"], relief="flat", bd=0,
                                 cursor="hand2", padx=8, pady=2, takefocus=True,
                                 highlightthickness=0)
        menu = tk.Menu(examples, tearoff=False, font=self.f_mono, bg=c["card"], fg=c["text"],
                       activebackground=c["select"], activeforeground=c["text"], bd=1)
        for sample in EXAMPLES:
            menu.add_command(label=sample, command=lambda s=sample: self.load(s, run=True))
        examples.configure(menu=menu)
        examples.pack(side="right")
        Tooltip(examples, "Tayyor ifodani tanlang — darhol hisoblanadi", self)

        # Bir qatorli Text: xato joyini ranglab ko'rsatish uchun Entry o'rniga
        line = tk.Frame(box, bg=c["card"])
        line.pack(fill="x", pady=(8, 4))
        FlatButton(line, self, "Hisoblash", self.compute, "primary", self.f_h2, "Enter",
                   padx=16).pack(side="right", fill="y", padx=(8, 0))
        frame = tk.Frame(line, bg=c["border"])
        frame.pack(side="left", fill="x", expand=True)
        self.entry_frame = frame
        self.entry = tk.Text(frame, height=1, width=1, wrap="none", font=self.f_input, bd=0,
                             bg=c["card"], fg=c["text"], insertbackground=c["accent"],
                             insertwidth=2, padx=12, pady=10, undo=True,
                             selectbackground=c["select"], selectforeground=c["text"],
                             highlightthickness=0)
        self.entry.pack(fill="x", padx=1, pady=1)
        self.entry.tag_configure("error", background=c["error_soft"], foreground=c["error"],
                                 underline=True)
        self.entry.tag_configure("hl", background=c["accent_soft"])
        self.entry.bind("<Return>", lambda _e: (self.compute(), "break")[1])
        self.entry.bind("<KP_Enter>", lambda _e: (self.compute(), "break")[1])
        self.entry.bind("<Up>", lambda _e: (self.history_step(-1), "break")[1])
        self.entry.bind("<Down>", lambda _e: (self.history_step(1), "break")[1])
        self.entry.bind("<Tab>", lambda _e: (self.entry.tk_focusNext().focus_set(), "break")[1])
        self.entry.bind("<Control-t>", lambda _e: (self.toggle_theme(), "break")[1])
        self.entry.bind("<<Modified>>", self._on_modified)
        self.entry.bind("<<Paste>>", self._on_paste)
        self.entry.bind("<FocusIn>", lambda _e: frame.configure(bg=c["accent"]))
        self.entry.bind("<FocusOut>", lambda _e: frame.configure(bg=c["border"]))

        self.status = self.label(box, "", "small", wraplength=370)
        self.status.pack(fill="x")
        tk.Frame(box, bg=c["border"], height=1).pack(fill="x", pady=10)

        row = tk.Frame(box, bg=c["card"])
        row.pack(fill="x")
        self.label(row, "POLIZ ko'rinishi", "h2").pack(side="left")
        FlatButton(row, self, "Nusxa", lambda: self.copy(self.result.poliz_text if self.result else ""),
                   "ghost", self.f_small, "POLIZ ni nusxalash", padx=8).pack(side="right")
        self.poliz_view = tk.Text(box, height=1, width=1, wrap="word", font=self.f_mono, bd=0,
                                  bg=c["card"], fg=c["text"], highlightthickness=0,
                                  cursor="arrow", padx=0, pady=4, spacing1=3, spacing3=3,
                                  takefocus=False)
        self.poliz_view.pack(fill="x")
        self.poliz_view.tag_configure("num", background=c["num_chip"])
        self.poliz_view.tag_configure("op", background=c["op_chip"], foreground=c["accent"])
        self.poliz_view.tag_configure("muted", foreground=c["muted"], font=self.f_body)
        self.poliz_view.configure(state="disabled")

        row = tk.Frame(box, bg=c["card"])
        row.pack(fill="x", pady=(8, 0))
        self.label(row, "Natija", "h2").pack(side="left")
        FlatButton(row, self, "Nusxa", lambda: self.copy(self.result.value_text if self.result else ""),
                   "ghost", self.f_small, "Natijani nusxalash (Ctrl+Shift+C)",
                   padx=8).pack(side="right")
        self.result_label = self.label(box, "—", "result")
        self.result_label.pack(fill="x")

    def _build_keypad(self, left):
        c = self.c
        box = self.card(left, row=1, column=0, sticky="nsew", pady=(12, 0))
        left.rowconfigure(1, weight=1)
        pad = tk.Frame(box, bg=c["card"])
        pad.pack(fill="both", expand=True)
        keys = [
            [("(", "("), (")", ")"), ("xʸ", " ^ "), ("⌫", "BACK")],
            [("7", "7"), ("8", "8"), ("9", "9"), ("÷", " / ")],
            [("4", "4"), ("5", "5"), ("6", "6"), ("×", " * ")],
            [("1", "1"), ("2", "2"), ("3", "3"), ("−", " - ")],
            [("0", "0"), (".", "."), ("C", "CLEAR"), ("+", " + ")],
        ]
        tips = {"BACK": "Oxirgi belgini o'chirish", "CLEAR": "Tozalash (Esc)",
                " ^ ": "Darajaga ko'tarish"}
        for r, row in enumerate(keys):
            pad.rowconfigure(r, weight=1, uniform="r")
            for col, (text, val) in enumerate(row):
                pad.columnconfigure(col, weight=1, uniform="k")
                kind = "op" if val.strip() in "+-*/^()" or val in ("BACK", "CLEAR") else "key"
                FlatButton(pad, self, text, lambda v=val: self.press(v), kind, self.f_key,
                           tips.get(val), pady=4, takefocus=False
                           ).grid(row=r, column=col, sticky="nsew", padx=3, pady=3)

    def _build_tabs(self, main):
        c = self.c
        self.tabs = ttk.Notebook(main)
        self.tabs.grid(row=1, column=1, sticky="nsew")

        conv = tk.Frame(self.tabs, bg=c["card"], padx=12, pady=12)
        self.conv_table = self._table(conv, [("№", 40, "center"), ("Token", 72, "center"),
                                             ("Amal", 250, "w"), ("Stek", 110, "w"),
                                             ("Chiqish (POLIZ)", 170, "w")])
        self.tabs.add(conv, text="1. POLIZ ga o'tkazish")

        ev = tk.Frame(self.tabs, bg=c["card"], padx=12, pady=12)
        self.eval_table = self._table(ev, [("№", 40, "center"), ("Token", 72, "center"),
                                           ("Amal", 260, "w"), ("Stek", 200, "w")])
        self.tabs.add(ev, text="2. Hisoblash")

        tr = tk.Frame(self.tabs, bg=c["card"])
        self.canvas = tk.Canvas(tr, bg=c["card"], highlightthickness=0)
        ys = ttk.Scrollbar(tr, orient="vertical", command=self.canvas.yview)
        xs = ttk.Scrollbar(tr, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        tr.rowconfigure(0, weight=1)
        tr.columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", lambda _e: self.draw_tree())
        self.tabs.add(tr, text="3. Ifoda daraxti")

        hist = tk.Frame(self.tabs, bg=c["card"], padx=12, pady=12)
        bar = tk.Frame(hist, bg=c["card"])
        bar.pack(fill="x", pady=(0, 8))
        self.label(bar, "Ikki marta bosing yoki Enter — ifodani qayta yuklash", "small").pack(side="left")
        FlatButton(bar, self, "Tarixni tozalash", self.clear_history, "ghost", self.f_small,
                   padx=8).pack(side="right")
        self.hist_table = self._table(hist, [("Ifoda", 260, "w"), ("POLIZ", 200, "w"),
                                             ("Natija", 90, "e")])
        self.hist_table.bind("<Double-1>", self._load_from_history)
        self.hist_table.bind("<Return>", self._load_from_history)
        self.tabs.add(hist, text="Tarix")

        for table in (self.conv_table, self.eval_table):
            table.bind("<<TreeviewSelect>>", self._on_step_select)

    def _table(self, master, columns) -> ttk.Treeview:
        inner = tk.Frame(master, bg=self.c["card"])
        inner.pack(fill="both", expand=True)
        ids = [f"c{i}" for i in range(len(columns))]
        tv = ttk.Treeview(inner, columns=ids, show="headings", selectmode="browse")
        for cid, (title, width, anchor) in zip(ids, columns):
            tv.heading(cid, text=title, anchor=anchor)
            tv.column(cid, width=width, minwidth=40, anchor=anchor,
                      stretch=anchor == "w")
        tv.tag_configure("alt", background=self.c["row_alt"])
        tv.tag_configure("final", foreground=self.c["accent"])
        ys = ttk.Scrollbar(inner, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=ys.set)
        tv.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        return tv

    def _build_statusbar(self):
        c = self.c
        bar = tk.Frame(self.root, bg=c["card"], padx=20, pady=6)
        bar.pack(fill="x", side="bottom", before=self.main_frame)
        tk.Frame(self.root, bg=c["border"], height=1).pack(fill="x", side="bottom",
                                                           before=self.main_frame)
        hints = ("Enter — hisoblash   ·   Esc — tozalash   ·   ↑/↓ — tarix   ·   "
                 "Ctrl+Shift+C — natijani nusxalash   ·   F1 — qo'llanma")
        self.label(bar, hints, "small").pack(side="left")
        self.toast = self.label(bar, "", "small", fg=c["success"])
        self.toast.pack(side="right")

    # ------------------------------------------------------------ kiritish

    def get_expr(self) -> str:
        return self.entry.get("1.0", "end-1c")

    def focus_input(self):
        self.entry.focus_set()
        self.entry.mark_set("insert", "end-1c")
        self.entry.see("insert")

    def load(self, expr: str, run: bool = False):
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", expr)
        self.entry.edit_modified(False)  # jonli hisoblash compute() natijasini bosib ketmasin
        self.focus_input()
        if run:
            self.compute()
        else:
            self.live_preview()

    def press(self, value: str):
        if value == "CLEAR":
            self.clear()
            return
        if value == "BACK":
            if self.entry.tag_ranges("sel"):
                self.entry.delete("sel.first", "sel.last")
            else:
                # " + " bitta tugma bilan qo'shilgani uchun bo'shliqlari bilan birga o'chadi
                before = self.entry.get("1.0", "insert").rstrip()
                kept = before[:-1]
                if before[-1:] in "+-*/^":
                    kept = kept.rstrip()
                self.entry.delete(f"1.{len(kept)}", "insert")
        else:
            if self.entry.tag_ranges("sel"):
                self.entry.delete("sel.first", "sel.last")
            before = self.entry.get("1.0", "insert")
            if value.startswith(" ") and (not before or before.endswith(" ")):
                value = value.lstrip()
            self.entry.insert("insert", value)
        self.entry.focus_set()

    def _on_paste(self, _e):
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            return "break"
        if self.entry.tag_ranges("sel"):
            self.entry.delete("sel.first", "sel.last")
        self.entry.insert("insert", " ".join(text.split()))
        return "break"

    def _on_modified(self, _e=None):
        if not self.entry.edit_modified():
            return
        self.entry.edit_modified(False)
        self.entry.tag_remove("error", "1.0", "end")
        self.entry.tag_remove("hl", "1.0", "end")
        if self.live_job:
            self.root.after_cancel(self.live_job)
        self.live_job = self.root.after(LIVE_DELAY_MS, self.live_preview)

    def clear(self):
        self.entry.delete("1.0", "end")
        self.result = None
        self.history_index = None
        self.show_placeholder()
        self.focus_input()

    # ------------------------------------------------------------ hisoblash

    def live_preview(self):
        """Yozish davomida natijani ko'rsatadi; xatolarni faqat Enter bosilganda ochiq aytadi."""
        self.live_job = None
        expr = self.get_expr()
        if not expr.strip():
            self.result = None
            self.show_placeholder()
            return
        try:
            res = calculate(expr)
        except PolizError:
            self.result = None
            self.show_placeholder(keep_status=True)
            self.set_status("Kiritishni davom ettiring…  Enter — tekshirish")
            return
        self.result = res
        self.show_result(res)
        self.set_status("✓ Ifoda to'g'ri", "success")

    def compute(self):
        if self.live_job:
            self.root.after_cancel(self.live_job)
            self.live_job = None
        expr = self.get_expr()
        try:
            res = calculate(expr)
        except PolizError as err:
            self.result = None
            self.show_placeholder(keep_status=True)
            self.show_error(err)
            return
        self.result = res
        self.show_result(res)
        self.set_status("✓ Hisoblandi", "success")
        self.add_history(res)
        self.history_index = None

    def show_error(self, err: PolizError):
        self.entry.tag_remove("error", "1.0", "end")
        where = ""
        if err.pos is not None:
            self.entry.tag_add("error", f"1.{err.pos}", f"1.{err.pos + err.length}")
            self.entry.see(f"1.{err.pos}")
            self.entry.mark_set("insert", f"1.{err.pos}")
            where = f"  ({err.pos + 1}-belgi)"
        self.set_status(f"⚠  {err.message}{where}", "error")
        self.entry.focus_set()
        self._flash_border()

    def _flash_border(self, n: int = 0):
        colors = [self.c["error"], self.c["accent"]]
        if n < 4 and self.entry_frame.winfo_exists():
            self.entry_frame.configure(bg=colors[n % 2])
            self.root.after(120, self._flash_border, n + 1)

    def set_status(self, text: str, kind: str = "muted"):
        self.status.configure(text=text, fg=self.c[kind])

    # ------------------------------------------------------------ ko'rsatish

    def show_placeholder(self, keep_status: bool = False):
        self._set_poliz([])
        self.result_label.configure(text="—", fg=self.c["muted"])
        for tv in (self.conv_table, self.eval_table):
            tv.delete(*tv.get_children())
        self.draw_tree()
        if not keep_status:
            self.set_status("Masalan: (3 + 4) * 2 - (-5).  Raqamlarni klaviaturadan yoki "
                            "tugmalardan kiriting.")

    def show_result(self, res: Result):
        self._set_poliz(res.poliz)
        self.result_label.configure(text=res.value_text, fg=self.c["text"])
        self._fill(self.conv_table, [
            (i, s.token, s.action, " ".join(s.stack) or "∅", " ".join(s.output))
            for i, s in enumerate(res.convert_steps, 1)])
        self._fill(self.eval_table, [
            (i, s.token, s.action, " ".join(s.stack))
            for i, s in enumerate(res.eval_steps, 1)])
        self.draw_tree()

    def _fill(self, tv: ttk.Treeview, rows):
        tv.delete(*tv.get_children())
        for i, row in enumerate(rows):
            tags = ["alt"] if i % 2 else []
            if i == len(rows) - 1:
                tags.append("final")
            tv.insert("", "end", iid=str(i), values=row, tags=tags)

    def _set_poliz(self, tokens):
        v = self.poliz_view
        v.configure(state="normal")
        v.delete("1.0", "end")
        if not tokens:
            v.insert("end", "Ifoda hisoblangach shu yerda paydo bo'ladi", "muted")
        for t in tokens:
            v.insert("end", f" {t.text} ", "num" if t.kind == "num" else "op")
            v.insert("end", "  ")
        v.update_idletasks()
        lines = v.count("1.0", "end", "displaylines") or (1,)
        v.configure(state="disabled", height=min(4, max(1, lines[0])))

    def _on_step_select(self, event):
        tv = event.widget
        sel = tv.selection()
        self.entry.tag_remove("hl", "1.0", "end")
        if not sel or not self.result:
            return
        steps = self.result.convert_steps if tv is self.conv_table else self.result.eval_steps
        step = steps[int(sel[0])]
        if step.pos is not None:
            self.entry.tag_add("hl", f"1.{step.pos}", f"1.{step.pos + step.length}")
            self.entry.see(f"1.{step.pos}")

    # ------------------------------------------------------------ daraxt

    def draw_tree(self):
        cv = self.canvas
        if not cv.winfo_exists():
            return
        cv.delete("all")
        c = self.c
        if not self.result:
            cv.configure(scrollregion=(0, 0, 0, 0))
            cv.create_text(cv.winfo_width() // 2, cv.winfo_height() // 2,
                           text="Ifoda daraxti hisoblashdan keyin chiziladi",
                           fill=c["muted"], font=self.f_body)
            return

        f = tkfont.Font(font=self.f_mono)
        leaf_x = [0]
        layout = []  # (node, x, depth, width)

        def place(node, depth):
            w = max(38, f.measure(node.label) + 22)
            if not node.children:
                x = leaf_x[0] + w / 2
                leaf_x[0] += w + 18
            else:
                xs = [place(ch, depth + 1) for ch in node.children]
                x = sum(xs) / len(xs)
                if len(node.children) == 1:
                    leaf_x[0] = max(leaf_x[0], x + w / 2 + 18)
            layout.append((node, x, depth, w))
            return x

        place(self.result.tree, 0)
        level_h, node_h, margin = 70, 34, 30
        top = 50
        width = leaf_x[0] - 18 + 2 * margin
        depth = max(d for _, _, d, _ in layout)
        height = depth * level_h + node_h + 2 * margin
        ox = max(margin, (cv.winfo_width() - width) / 2 + margin)
        oy = top
        pos = {id(n): (ox + x, oy + d * level_h + node_h / 2) for n, x, d, _ in layout}

        for n, *_ in layout:
            x1, y1 = pos[id(n)]
            for ch in n.children:
                x2, y2 = pos[id(ch)]
                cv.create_line(x1, y1, x2, y2, fill=c["tree_line"], width=2)
        for n, _, _, w in layout:
            x, y = pos[id(n)]
            is_op = bool(n.children)
            fill = c["accent"] if is_op else c["num_chip"]
            fg = c["accent_text"] if is_op else c["text"]
            self._round_rect(x - w / 2, y - node_h / 2, x + w / 2, y + node_h / 2, 12,
                             fill=fill, outline=c["accent"] if is_op else c["border"])
            cv.create_text(x, y, text=n.label, fill=fg, font=self.f_mono)

        cv.create_text(12, 12, anchor="nw", fill=c["muted"], font=self.f_small,
                       text="Daraxtni pastdan yuqoriga, chapdan o'ngga aylanib o'qisangiz — POLIZ hosil bo'ladi")
        cv.configure(scrollregion=(0, 0, max(width + ox, cv.winfo_width()),
                                   max(height + oy, cv.winfo_height())))

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    # ------------------------------------------------------------ tarix

    def _load_history(self) -> list[dict]:
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return [h for h in data if {"expr", "poliz", "value"} <= h.keys()][:HISTORY_LIMIT]
        except (OSError, ValueError, AttributeError, TypeError):
            return []

    def _save_history(self):
        try:
            HISTORY_FILE.write_text(json.dumps(self.history, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
        except OSError:
            pass  # tarixni saqlab bo'lmasa ham ilova ishlashda davom etadi

    def add_history(self, res: Result):
        item = {"expr": res.expression.strip(), "poliz": res.poliz_text, "value": res.value_text}
        self.history = [h for h in self.history if h["expr"] != item["expr"]]
        self.history.insert(0, item)
        del self.history[HISTORY_LIMIT:]
        self._save_history()
        self.render_history()

    def render_history(self):
        self._fill(self.hist_table, [(h["expr"], h["poliz"], h["value"]) for h in self.history])
        for iid in self.hist_table.get_children():
            self.hist_table.item(iid, tags=["alt"] if int(iid) % 2 else [])
        title = f"Tarix ({len(self.history)})" if self.history else "Tarix"
        self.tabs.tab(3, text=title)

    def clear_history(self):
        self.history = []
        self._save_history()
        self.render_history()
        self.notify("Tarix tozalandi")

    def _load_from_history(self, _e=None):
        sel = self.hist_table.selection()
        if sel:
            self.load(self.history[int(sel[0])]["expr"], run=True)
            self.tabs.select(0)

    def history_step(self, delta: int):
        if not self.history:
            return
        if self.history_index is None:
            if delta > 0:
                return
            idx = 0
        else:
            idx = self.history_index - delta
            if idx >= len(self.history):
                idx = len(self.history) - 1
            if idx < 0:
                idx = None
        self.history_index = idx
        self.load(self.history[idx]["expr"] if idx is not None else "")

    # ------------------------------------------------------------ boshqalar

    def copy(self, text: str):
        if not text:
            self.notify("Nusxalash uchun avval ifodani hisoblang", "muted")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.notify(f"Nusxalandi: {text}")

    def notify(self, text: str, kind: str = "success"):
        self.toast.configure(text=text, fg=self.c[kind])
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.toast_job = self.root.after(2500, lambda: self.toast.winfo_exists()
                                         and self.toast.configure(text=""))

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.build()

    def show_help(self):
        c = self.c
        win = tk.Toplevel(self.root, bg=c["card"])
        win.title("Qo'llanma — POLIZ qanday ishlaydi")
        win.transient(self.root)
        win.geometry(f"720x620+{self.root.winfo_rootx() + 80}+{self.root.winfo_rooty() + 40}")
        txt = tk.Text(win, wrap="word", font=self.f_body, bg=c["card"], fg=c["text"],
                      bd=0, padx=24, pady=20, highlightthickness=0, spacing1=2, spacing3=2)
        ys = ttk.Scrollbar(win, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        txt.tag_configure("h", font=self.f_h2, foreground=c["accent"], spacing1=10)
        txt.tag_configure("code", font=(self.f_mono[0], 10))
        for line in HELP_TEXT.splitlines():
            if line.startswith("# "):
                txt.insert("end", line[2:] + "\n", "h")
            elif line.startswith("  ") and not line.lstrip().startswith("•"):
                txt.insert("end", line + "\n", "code")
            else:
                txt.insert("end", line + "\n")
        txt.configure(state="disabled")
        win.bind("<Escape>", lambda _e: win.destroy())
        win.focus_set()


def _enable_hidpi():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def main():
    _enable_hidpi()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
