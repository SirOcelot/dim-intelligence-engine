from __future__ import annotations

import tkinter as tk
from tkinter import ttk

APP_NAME = "Warmind"
APP_TAGLINE = "Destiny Intelligence Engine"
APP_VERSION_LABEL = "Premium UI"

PALETTE = {
    "bg": "#0F1117",
    "panel": "#171A22",
    "panel_alt": "#1D2230",
    "text": "#E8ECF4",
    "muted": "#9AA4B2",
    "accent": "#7C5CFF",
    "accent_alt": "#4CC9F0",
    "success": "#38D39F",
    "warning": "#F4B942",
    "danger": "#FF6B6B",
    "border": "#2B3243",
}

FONT_STACK = {
    "title": ("Segoe UI", 24, "bold"),
    "subtitle": ("Segoe UI", 10),
    "heading": ("Segoe UI", 11, "bold"),
    "body": ("Segoe UI", 10),
    "mono": ("Cascadia Code", 10),
    "button": ("Segoe UI", 10, "bold"),
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=PALETTE["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=PALETTE["bg"], foreground=PALETTE["text"], font=FONT_STACK["body"])
    style.configure("TFrame", background=PALETTE["bg"])
    style.configure("Card.TFrame", background=PALETTE["panel"], relief="flat", borderwidth=0)
    style.configure("AltCard.TFrame", background=PALETTE["panel_alt"], relief="flat", borderwidth=0)
    style.configure("TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=FONT_STACK["body"])
    style.configure("Muted.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"], font=FONT_STACK["subtitle"])
    style.configure("Title.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=FONT_STACK["title"])
    style.configure("Heading.TLabel", background=PALETTE["bg"], foreground=PALETTE["text"], font=FONT_STACK["heading"])
    style.configure("TLabelFrame", background=PALETTE["panel"], foreground=PALETTE["text"], bordercolor=PALETTE["border"])
    style.configure("TLabelFrame.Label", background=PALETTE["panel"], foreground=PALETTE["text"], font=FONT_STACK["heading"])
    style.configure("TEntry", fieldbackground=PALETTE["panel_alt"], foreground=PALETTE["text"], bordercolor=PALETTE["border"], insertcolor=PALETTE["text"])
    style.map("TEntry", bordercolor=[("focus", PALETTE["accent"])])
    style.configure("TCombobox", fieldbackground=PALETTE["panel_alt"], foreground=PALETTE["text"], bordercolor=PALETTE["border"], arrowsize=14)
    style.map("TCombobox", bordercolor=[("focus", PALETTE["accent"])])
    style.configure("TNotebook", background=PALETTE["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=PALETTE["panel"], foreground=PALETTE["muted"], padding=(14, 8), font=FONT_STACK["body"])
    style.map("TNotebook.Tab", background=[("selected", PALETTE["panel_alt"])], foreground=[("selected", PALETTE["text"])])
    style.configure("Primary.TButton", background=PALETTE["accent"], foreground="#FFFFFF", padding=(14, 10), font=FONT_STACK["button"], borderwidth=0)
    style.map("Primary.TButton", background=[("active", "#6B4DFF"), ("pressed", "#5C3FFF")])
    style.configure("Secondary.TButton", background=PALETTE["panel_alt"], foreground=PALETTE["text"], padding=(12, 9), font=FONT_STACK["button"], borderwidth=0)
    style.map("Secondary.TButton", background=[("active", "#252C3C"), ("pressed", "#202635")])
    style.configure("Danger.TButton", background=PALETTE["danger"], foreground="#FFFFFF", padding=(12, 9), font=FONT_STACK["button"], borderwidth=0)
    style.map("Danger.TButton", background=[("active", "#F25959"), ("pressed", "#E04C4C")])
    style.configure("TCheckbutton", background=PALETTE["bg"], foreground=PALETTE["text"], font=FONT_STACK["body"])
    style.map("TCheckbutton", foreground=[("active", PALETTE["text"])])
    return style


def style_text_widget(widget: tk.Text) -> None:
    widget.configure(
        bg=PALETTE["panel_alt"],
        fg=PALETTE["text"],
        insertbackground=PALETTE["text"],
        selectbackground=PALETTE["accent"],
        selectforeground="#FFFFFF",
        relief="flat",
        borderwidth=0,
        font=FONT_STACK["mono"],
        padx=12,
        pady=12,
    )


def set_status(label_var: tk.StringVar, message: str, state: str = "info") -> str:
    prefix = {
        "info": "●",
        "success": "●",
        "warning": "●",
        "danger": "●",
    }.get(state, "●")
    text = f"{prefix} {message}"
    label_var.set(text)
    return text


def get_status_color(state: str) -> str:
    return {
        "info": PALETTE["muted"],
        "success": PALETTE["success"],
        "warning": PALETTE["warning"],
        "danger": PALETTE["danger"],
    }.get(state, PALETTE["muted"])


def hero_copy() -> tuple[str, str]:
    return APP_NAME, f"{APP_TAGLINE} • Smarter loadouts, cleaner clears, faster decisions"
