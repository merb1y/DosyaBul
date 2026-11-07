"""Rofi '--dmenu' borulama (stdin -> seçim -> stdout) modu."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Iterable

from . import themes, usertheme
from .query import fuzzy_score
from .settings import SettingsStore
from .windowing import activate_window, apply_popup_style, popup_geometry

FONT_FAMILY = "Cascadia Code"
HEADER_HEIGHT = 52
PANEL_BORDER = 2


def filter_dmenu_lines(lines: Iterable[str], query: str) -> list[tuple[int, str]]:
    """Verilen satırları Rofi fuzzy_score ile filtreler; (orijinal_indeks, satır) döndürür."""
    items = [(idx, line) for idx, line in enumerate(lines)]
    q = (query or "").strip()
    if not q:
        return items
    scored: list[tuple[int, int, str]] = []
    for idx, line in items:
        score = fuzzy_score(q, line)
        if score is not None:
            scored.append((score, idx, line))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [(idx, line) for _, idx, line in scored]


def run_dmenu(
    lines: Iterable[str],
    *,
    prompt: str = "Seç:",
    data_dir: Path | None = None,
) -> tuple[int, str | None]:
    """Tkinter ile Rofi dmenu penceresi açar; (çıkış_kodu, seçilen_satır) döndürür."""
    clean_lines = [line.rstrip("\r\n") for line in lines if line.strip("\r\n")]
    settings_path = (data_dir / "settings.json") if data_dir else None
    settings = SettingsStore(settings_path).load() if settings_path else SettingsStore(Path.home() / ".dosyabul_dmenu.json").load()
    base_theme = themes.resolve(settings.theme)
    if settings.accent_color:
        base_theme = base_theme.with_colors(accent=settings.accent_color, border=settings.accent_color)
    if data_dir:
        base_theme = usertheme.apply_overrides(base_theme, usertheme.load_overrides(usertheme.theme_path(data_dir)))

    root = tk.Tk()
    root.withdraw()
    root.title("DosyaBul · dmenu")
    root.configure(bg=base_theme.background)
    apply_popup_style(root)
    try:
        root.attributes("-alpha", settings.opacity / 100)
    except tk.TclError:
        pass

    result_box: list[str | None] = [None]
    visible_rows = min(max(1, settings.visible_rows), max(1, len(clean_lines)))
    row_height = 36

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Dmenu.Treeview",
        font=(FONT_FAMILY, 10),
        rowheight=row_height,
        background=base_theme.background,
        fieldbackground=base_theme.background,
        foreground=base_theme.text,
        borderwidth=0,
        padding=0,
    )
    style.map("Dmenu.Treeview", background=[("selected", base_theme.surface)], foreground=[("selected", base_theme.text)])
    style.layout("Dmenu.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    border = tk.Frame(root, bg=base_theme.border)
    border.pack(fill="both", expand=True)
    main = tk.Frame(border, bg=base_theme.background)
    main.pack(fill="both", expand=True, padx=PANEL_BORDER, pady=PANEL_BORDER)
    main.columnconfigure(0, weight=1)
    main.rowconfigure(1, weight=1)

    header = tk.Frame(main, bg=base_theme.accent, height=HEADER_HEIGHT)
    header.grid(row=0, column=0, sticky="ew")
    header.pack_propagate(False)

    tk.Label(
        header,
        text=prompt or "dmenu",
        font=(FONT_FAMILY, 10, "bold"),
        bg=base_theme.accent,
        fg=base_theme.accent_text,
        padx=12,
    ).pack(side="left")

    query_var = tk.StringVar()
    entry = tk.Entry(
        header,
        textvariable=query_var,
        font=(FONT_FAMILY, 11),
        bg=base_theme.accent,
        fg=base_theme.accent_text,
        insertbackground=base_theme.accent_text,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
    )
    entry.pack(side="left", fill="both", expand=True, padx=(2, 10), pady=6)

    count_label = tk.Label(
        header,
        text=f"{len(clean_lines)}",
        font=(FONT_FAMILY, 9),
        bg=base_theme.accent,
        fg=base_theme.accent_text,
        padx=10,
    )
    count_label.pack(side="right")

    tree = ttk.Treeview(main, columns=(), show="tree", selectmode="browse", style="Dmenu.Treeview")
    tree.grid(row=1, column=0, sticky="nsew")

    current_items: list[tuple[int, str]] = []

    def refresh_list(*_args):
        nonlocal current_items
        current_items = filter_dmenu_lines(clean_lines, query_var.get())
        children = tree.get_children()
        if children:
            tree.delete(*children)
        for rank, (orig_idx, line) in enumerate(current_items):
            badge = f"[{rank + 1}]  " if rank < 9 else "     "
            tree.insert("", "end", iid=str(orig_idx), text=f"{badge}{line}")
        count_label.configure(text=f"{len(current_items)}/{len(clean_lines)}")
        if current_items:
            first_id = str(current_items[0][0])
            tree.selection_set(first_id)
            tree.focus(first_id)
        rows = min(visible_rows, max(1, len(current_items)))
        height = HEADER_HEIGHT + PANEL_BORDER * 2 + rows * row_height
        width, height, x, y = popup_geometry(root, height, settings.panel_width, settings.panel_position, settings.monitor_mode)
        root.geometry(f"{width}x{height}+{x}+{y}")

    def accept_selected(_event=None):
        sel = tree.selection()
        if sel:
            idx = int(sel[0])
            result_box[0] = clean_lines[idx]
        elif query_var.get().strip():
            result_box[0] = query_var.get().strip()
        root.destroy()
        return "break"

    def accept_index(rank: int):
        if 0 <= rank < len(current_items):
            result_box[0] = current_items[rank][1]
            root.destroy()
        return "break"

    def cancel(_event=None):
        result_box[0] = None
        root.destroy()
        return "break"

    def move(delta: int):
        children = tree.get_children()
        if not children:
            return "break"
        sel = tree.selection()
        cur = children.index(sel[0]) if sel and sel[0] in children else 0
        nxt = max(0, min(len(children) - 1, cur + delta))
        target = children[nxt]
        tree.selection_set(target)
        tree.focus(target)
        tree.see(target)
        return "break"

    query_var.trace_add("write", refresh_list)
    entry.bind("<Down>", lambda _e: move(1))
    entry.bind("<Up>", lambda _e: move(-1))
    entry.bind("<Control-j>", lambda _e: move(1))
    entry.bind("<Control-k>", lambda _e: move(-1))
    entry.bind("<Control-n>", lambda _e: move(1))
    entry.bind("<Control-p>", lambda _e: move(-1))
    entry.bind("<Return>", accept_selected)
    tree.bind("<Double-1>", accept_selected)
    tree.bind("<Return>", accept_selected)
    root.bind("<Escape>", cancel)
    for num in range(1, 10):
        root.bind(f"<Alt-Key-{num}>", lambda _e, r=num - 1: accept_index(r))

    refresh_list()
    activate_window(root)
    entry.focus_set()
    root.mainloop()

    if result_box[0] is not None:
        return 0, result_box[0]
    return 1, None
