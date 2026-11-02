"""Tek arama kutusu, kip sistemi ve sonuc listesi (Rofi benzeri)."""

import logging
import os
import queue
import threading
import time
import tkinter as tk
from concurrent.futures import CancelledError, ThreadPoolExecutor
from pathlib import Path
from tkinter import font as tkfont
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Iterable
from . import actions
from .applications import TERMINAL_CHOICES, ApplicationIndex, LauncherResults, ResultItem, launch_application, launch_terminal_command
from .database import IndexDatabase, SearchCancelled
from .drives import discover_drives
from .hotkey import MOD_WIN, VK_SPACE, HotkeyService, HotkeySpec, captured_hotkey, format_hotkey
from .indexer import Indexer
from .models import FileResult, ScanProgress, ScanReport, SearchResults
from .query import QueryError, fold_text, parse_plain_query
from .settings import MODE_CHOICES, MONITOR_CHOICES, POSITION_CHOICES, ROW_CHOICES, THEME_CHOICES, AppSettings, SettingsStore
from .startup import is_startup_enabled, set_startup
from . import themes
from .websearch import SEARCH_ENGINES, open_web, resolve_web_input
from .windowing import activate_window, active_work_area, apply_popup_style, popup_geometry
from . import windows as window_tools
from . import icons
from . import tray as tray_module

PLACEHOLDER = "Ara…"

MODE_ALL = "Tümü"
MODE_APPS = "Uygulamalar"
MODE_FILES = "Dosyalar"
MODE_COMMANDS = "Komutlar"
MODE_WEB = "Web"
MODE_WINDOWS = "Pencereler"

MODE_ORDER = (MODE_ALL, MODE_APPS, MODE_FILES, MODE_COMMANDS, MODE_WEB, MODE_WINDOWS)
MODE_LABELS = {
    MODE_ALL: "Uygulama · Dosya · Komut · Web",
    MODE_APPS: "Uygulama listesi",
    MODE_FILES: "Dosya ve klasör listesi",
    MODE_COMMANDS: "Komut çalıştır",
    MODE_WEB: "Web araması",
    MODE_WINDOWS: "Açık pencereler",
}
MODE_HINTS = {
    MODE_ALL: "Yazmaya başla · Ctrl+K kip değiştir",
    MODE_APPS: "Uygulama ara · Ctrl+K kip değiştir",
    MODE_FILES: "Dosya ve klasör ara · Ctrl+K kip değiştir",
    MODE_COMMANDS: "/komut yaz ve Enter'a bas",
    MODE_WEB: "!arama ya da !site.com yaz",
    MODE_WINDOWS: "Açık pencerelerden birini ara",
}

FONT_FAMILY = "Cascadia Code"
HEADER_HEIGHT = 54
PANEL_BORDER = 2
MAX_RESULTS = 500
APP_ICON_SIZE = 28


def format_count(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def path_key(path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _scaled(value: int, scale: int) -> int:
    return max(1, (value * scale + 50) // 100)


class FinderApp:
    """Rofi tarzı tek kutulu arama paneli."""

    def __init__(
        self,
        root: tk.Tk,
        database: IndexDatabase,
        *,
        drive_provider: Callable[[], Iterable[Path]] = discover_drives,
        auto_start: bool = True,
        start_hidden: bool = False,
        enable_hotkey: bool = True,
        activation_checker: Callable[[], bool] | None = None,
        settings_store: SettingsStore | None = None,
        application_index: ApplicationIndex | None = None,
        enable_tray: bool = True,
    ):
        self.root = root
        self.database = database
        self.drive_provider = drive_provider
        self.auto_start = auto_start
        self.start_hidden = start_hidden
        self.activation_checker = activation_checker
        self.settings_store = settings_store or SettingsStore(database.path.parent / "settings.json")
        self.settings = self.settings_store.load()
        self.applications = application_index or ApplicationIndex()
        # Eski test/uyum bekleyen ad.
        self.application_index = self.applications
        self.events: queue.Queue = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="DosyaBul-Arama")
        self.items: dict[str, ResultItem] = {}
        self._drive_paths: tuple[str, ...] = ()
        self._search_generation = 0
        self._last_results_generation = -1
        self._pending_open_generation = None
        self._search_cancel: threading.Event | None = None
        self._search_future = None
        self._search_after = None
        self._event_after = None
        self._auto_after = None
        self._toast_after = None
        self._focus_after = None
        self._scan_thread: threading.Thread | None = None
        self._app_thread: threading.Thread | None = None
        self._scan_cancel = threading.Event()
        self._scanning = False
        self._closing = False
        self._quitting = False
        self._last_typing = 0.0
        self._last_live_refresh = 0.0
        self._shown = False
        self._suspend_hide = False
        self._result_rows = 0
        self._mode = self.settings.default_mode
        self._hotkey_enabled = enable_hotkey
        self._tray_enabled = enable_tray
        self._hotkey = HotkeyService(lambda: self.events.put(("toggle",)), spec=self.settings.hotkey_spec) if enable_hotkey else None
        self.hotkey_available = False
        self._settings_window = None
        self._settings_hotkey_spec: HotkeySpec | None = None
        self._theme = self._resolve_theme()
        self._icon_cache: dict[str, object] = {}
        self._tray = None
        self._idle_status = self._ready_status()

        root.title("DosyaBul")
        root.configure(bg=self._theme.background)
        self.query_var = tk.StringVar()
        self.status_var = tk.StringVar(value=self._idle_status)
        self.selected_path_var = tk.StringVar()
        self.mode_var = tk.StringVar(value=self._mode)
        self._configure_styles()
        self._build_interface()
        apply_popup_style(root)
        root.attributes("-alpha", self.settings.opacity / 100)
        self._bind_shortcuts()
        self.query_var.trace_add("write", self._query_changed)
        self._event_after = root.after(50, self._drain_events)
        if auto_start:
            self._start_application_refresh()
            if self._needs_initial_scan() or self.settings.refresh_on_start:
                self._auto_after = root.after(80, self.start_scan)
        root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        if self._hotkey:
            self.hotkey_available = self._hotkey.start()
            if not self.hotkey_available:
                logging.warning("%s genel kısayolu kaydedilemedi: %s", self.settings.hotkey, self._hotkey.error)
                self._idle_status = "Genel kısayol başka bir uygulama tarafından kullanılıyor."
                if not auto_start:
                    self.status_var.set(self._idle_status)
        if start_hidden:
            root.withdraw()
        else:
            root.after(90, self.show_popup)
        if self._tray_enabled:
            self.setup_tray()

    # ---- Görünüm --------------------------------------------------------

    def _ready_status(self) -> str:
        return f"{self.settings.hotkey} · Esc gizle" if self.hotkey_available else "Hazır"

    def _resolve_theme(self):
        base = themes.resolve(self.settings.theme)
        accent = self.settings.accent_color
        if accent:
            return base.with_colors(accent=accent, border=accent)
        return base

    def _palette(self):
        return self._theme

    def _configure_styles(self):
        theme = self._palette()
        for named in ("TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
            try:
                tkfont.nametofont(named, root=self.root).configure(family=FONT_FAMILY)
            except tk.TclError:
                pass
        self.root.option_add("*Font", (FONT_FAMILY, 10))
        text_font = tkfont.Font(root=self.root, family=FONT_FAMILY, size=10)
        self._line_height = text_font.metrics("linespace")
        self._row_height = max(34, _scaled(self._line_height + 23, self.settings.row_scale))
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Results.Treeview", font=(FONT_FAMILY, 10), rowheight=self._row_height,
                        background=theme.background, fieldbackground=theme.background, foreground=theme.text, borderwidth=0, padding=0)
        style.map("Results.Treeview", background=[("selected", theme.surface)], foreground=[("selected", theme.text)])
        style.layout("Results.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.configure("Settings.TCombobox", font=(FONT_FAMILY, 10), fieldbackground=theme.surface, background=theme.surface,
                        foreground=theme.text, arrowcolor=theme.border, bordercolor=theme.border, padding=6)
        style.map("Settings.TCombobox", fieldbackground=[("readonly", theme.surface)], foreground=[("readonly", theme.text)],
                  selectbackground=[("readonly", theme.surface)], selectforeground=[("readonly", theme.text)])

    def _make_icons(self):
        theme = self._palette()
        folder = tk.PhotoImage(master=self.root, width=16, height=16)
        folder.put("#F2CDCD", to=(1, 3, 7, 6))
        folder.put("#E8A2AF", to=(1, 5, 15, 13))
        folder.put("#F2CDCD", to=(2, 6, 14, 12))
        file_icon = tk.PhotoImage(master=self.root, width=16, height=16)
        file_icon.put("#89DCEB", to=(4, 2, 12, 14))
        file_icon.put("#29283D", to=(5, 3, 11, 13))
        file_icon.put("#89DCEB", to=(6, 7, 10, 8))
        file_icon.put("#89DCEB", to=(6, 10, 10, 11))
        application = tk.PhotoImage(master=self.root, width=16, height=16)
        application.put("#CBA6F7", to=(2, 2, 7, 7))
        application.put("#89DCEB", to=(9, 2, 14, 7))
        application.put("#A6E3A1", to=(2, 9, 7, 14))
        application.put("#F9E2AF", to=(9, 9, 14, 14))
        terminal = tk.PhotoImage(master=self.root, width=16, height=16)
        terminal.put("#A6E3A1", to=(1, 2, 15, 14))
        terminal.put(theme.background, to=(2, 3, 14, 13))
        terminal.put("#A6E3A1", to=(4, 6, 6, 8))
        terminal.put("#A6E3A1", to=(7, 9, 11, 10))
        settings = tk.PhotoImage(master=self.root, width=16, height=16)
        settings.put("#F9E2AF", to=(3, 3, 13, 13))
        settings.put(theme.background, to=(6, 6, 10, 10))
        web = tk.PhotoImage(master=self.root, width=16, height=16)
        web.put("#89B4FA", to=(3, 2, 13, 14))
        web.put(theme.background, to=(4, 3, 12, 13))
        web.put("#89B4FA", to=(2, 6, 14, 10))
        web.put(theme.background, to=(3, 7, 13, 9))
        web.put("#89B4FA", to=(7, 2, 9, 14))
        window_icon = tk.PhotoImage(master=self.root, width=16, height=16)
        window_icon.put("#89DCEB", to=(2, 3, 14, 14))
        window_icon.put(theme.background, to=(3, 5, 13, 13))
        window_icon.put("#89DCEB", to=(2, 3, 14, 5))
        scale = 2 if self._line_height > 24 else 1
        self._folder_icon = self._pad_icon(folder.zoom(scale))
        self._file_icon = self._pad_icon(file_icon.zoom(scale))
        self._app_icon = self._pad_icon(application.zoom(scale))
        self._terminal_icon = self._pad_icon(terminal.zoom(scale))
        self._settings_icon = self._pad_icon(settings.zoom(scale))
        self._web_icon = self._pad_icon(web.zoom(scale))
        self._window_icon = self._pad_icon(window_icon.zoom(scale))

    def _pad_icon(self, image):
        """İkon ile sonuç adı arasında Rofi'deki gibi nefes payı bırakır."""
        padded = tk.PhotoImage(master=self.root, width=image.width() + 10, height=image.height())
        self.root.tk.call(padded, "copy", image)
        return padded

    def _rgba_photo(self, width, height, rgba, background):
        """RGBA baytlarını, arka planla harmanlayarak Tk PhotoImage yapar."""
        bg_r, bg_g, bg_b = int(background[1:3], 16), int(background[3:5], 16), int(background[5:7], 16)
        image = tk.PhotoImage(master=self.root, width=width, height=height)
        rows = []
        for index in range(0, len(rgba), 4):
            r, g, b, a = rgba[index], rgba[index + 1], rgba[index + 2], rgba[index + 3]
            if a != 255:
                r = (r * a + bg_r * (255 - a)) // 255
                g = (g * a + bg_g * (255 - a)) // 255
                b = (b * a + bg_b * (255 - a)) // 255
            rows.append(f"#{r:02x}{g:02x}{b:02x}")
        for y in range(height):
            chunk = " ".join(rows[y * width:(y + 1) * width])
            image.put("{" + chunk + "}", to=(0, y))
        return image

    def _load_app_icon(self, path):
        """Bir uygulama/kısayol yolundan gerçek ikonu yükler (önbellekli)."""
        key = str(path).casefold()
        if key in self._icon_cache:
            return self._icon_cache[key]
        image = None
        data = icons.load_icon(path)
        if data is not None:
            width, height, rgba = data
            image = self._rgba_photo(width, height, rgba, self._theme.background)
            image = self._pad_icon(image)
        self._icon_cache[key] = image
        return image

    def _build_interface(self):
        theme = self._palette()
        self.panel_border = tk.Frame(self.root, bg=theme.border)
        border = self.panel_border
        border.pack(fill="both", expand=True)
        self.main_frame = tk.Frame(border, bg=theme.background)
        main = self.main_frame
        main.pack(fill="both", expand=True, padx=PANEL_BORDER, pady=PANEL_BORDER)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        # Rofi'nin "type-2" görünümü: arama alanı pencerenin üstüne tam oturur,
        # vurgu rengiyle kaplanır; sonuçlar hemen altında akar.
        self.search_box = tk.Frame(main, bg=theme.accent, height=HEADER_HEIGHT)
        search_box = self.search_box
        search_box.grid(row=0, column=0, sticky="ew")
        search_box.pack_propagate(False)
        self.search_canvas = tk.Canvas(search_box, width=32, height=HEADER_HEIGHT, bg=theme.accent, highlightthickness=0)
        icon = self.search_canvas
        icon.pack(side="left", padx=(10, 0))
        self._search_oval = icon.create_oval(8, 14, 20, 26, outline=theme.accent_text, width=2)
        self._search_line = icon.create_line(19, 25, 26, 32, fill=theme.accent_text, width=2)
        self.entry_box = tk.Frame(search_box, bg=theme.accent)
        entry_box = self.entry_box
        entry_box.pack(side="left", fill="both", expand=True)
        self.search_entry = tk.Entry(entry_box, textvariable=self.query_var, font=(FONT_FAMILY, 11), bg=theme.accent,
                                     fg=theme.accent_text, insertbackground=theme.accent_text, selectbackground=theme.background,
                                     selectforeground=theme.accent_text, relief="flat", borderwidth=0, highlightthickness=0)
        self.search_entry.pack(fill="both", expand=True, padx=(2, 10), pady=6)
        self.placeholder = tk.Label(entry_box, text=PLACEHOLDER, font=(FONT_FAMILY, 11), bg=theme.accent, fg=theme.text, anchor="w", cursor="xterm")
        self.placeholder.place(x=5, rely=0.5, anchor="w")
        self.placeholder.bind("<Button-1>", self.focus_search)
        self.mode_chip = tk.Label(search_box, text=self._mode, font=(FONT_FAMILY, 9), bg=theme.accent, fg=theme.accent_text, anchor="e", cursor="hand2")
        self.mode_chip.pack(side="right", padx=(6, 12))
        self.mode_chip.bind("<Button-1>", self.cycle_mode)

        self.table_box = tk.Frame(main, bg=theme.background)
        self.table_box.grid(row=1, column=0, sticky="nsew")
        self.table_box.columnconfigure(0, weight=1)
        self.table_box.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(self.table_box, columns=(), show="tree", selectmode="browse", style="Results.Treeview", takefocus=True)
        self.tree.column("#0", width=600, minwidth=260, stretch=True)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=12, pady=0)
        self._make_icons()
        self.empty_label = tk.Label(self.table_box, text="Aramak için yazmaya başla", font=(FONT_FAMILY, 9), bg=theme.background, fg=theme.muted, wraplength=360, justify="center")
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        self.tree.bind("<Double-1>", self._double_click)
        self.tree.bind("<Button-3>", self._context_menu)

        self.context_menu = tk.Menu(self.root, tearoff=False, font=(FONT_FAMILY, 10))
        self.context_menu.add_command(label="Aç", command=self.open_selected)
        self.context_menu.add_command(label="Klasörde göster", command=self.reveal_selected)
        self.context_menu.add_command(label="Yolu kopyala", command=self.copy_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Ayarlar    Ctrl+,", command=self.open_settings)
        self.table_box.grid_remove()

    def _bind_shortcuts(self):
        for shortcut in ("<Control-k>", "<Control-f>", "<F3>"):
            self.root.bind(shortcut, self.focus_search)
        self.root.bind("<Control-Tab>", self.cycle_mode)
        self.root.bind("<F5>", self.refresh_all)
        self.root.bind("<Escape>", self.hide_popup)
        self.root.bind("<Control-q>", lambda _event: self.close())
        self.root.bind("<Control-comma>", self.open_settings)
        self.root.bind("<FocusOut>", self._focus_lost)
        self.search_entry.bind("<Down>", lambda _event: self._move_selection(1))
        self.search_entry.bind("<Up>", lambda _event: self._move_selection(-1))
        self.search_entry.bind("<Control-j>", lambda _event: self._move_selection(1))
        self.search_entry.bind("<Control-n>", lambda _event: self._move_selection(1))
        self.search_entry.bind("<Control-p>", lambda _event: self._move_selection(-1))
        self.search_entry.bind("<Return>", self._open_search_result)
        self.search_entry.bind("<Shift-Return>", lambda _event: self.reveal_selected())
        self.search_entry.bind("<Tab>", self.cycle_mode)
        self.tree.bind("<Return>", lambda _event: self.open_selected())
        self.tree.bind("<Shift-Return>", lambda _event: self.reveal_selected())
        self.tree.bind("<Control-c>", lambda _event: self.copy_selected())

    # ---- Görünürlük -----------------------------------------------------

    @property
    def visible(self) -> bool:
        return self._shown and self.root.state() != "withdrawn"

    def _panel_height(self, rows: int | None = None) -> int:
        if not self.query_var.get().strip() and not self._show_rows_when_empty():
            return HEADER_HEIGHT + PANEL_BORDER * 2
        rows = self._result_rows if rows is None else rows
        return HEADER_HEIGHT + PANEL_BORDER * 2 + max(1, min(self.settings.visible_rows, rows)) * self._row_height

    def _show_rows_when_empty(self) -> bool:
        return self._mode in (MODE_COMMANDS, MODE_WEB, MODE_WINDOWS)

    def _position_popup(self, rows: int | None = None):
        width, height, x, y = popup_geometry(
            self.root, self._panel_height(rows), self.settings.panel_width,
            self.settings.panel_position, self.settings.monitor_mode,
        )
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def show_popup(self, *_args):
        if self._closing:
            return "break"
        self._shown = True
        self._cancel_timer("_focus_after")
        if self.query_var.get().strip() or self._show_rows_when_empty():
            self.table_box.grid()
        else:
            self.table_box.grid_remove()
        self._position_popup()
        activate_window(self.root)
        self.focus_search()
        return "break"

    def hide_popup(self, _event=None, *, clear=True):
        if self._closing:
            return "break"
        self._shown = False
        self._cancel_timer("_focus_after")
        self.root.withdraw()
        if clear and self.query_var.get():
            self.query_var.set("")
        return "break"

    def toggle_popup(self):
        return self.hide_popup() if self.visible else self.show_popup()

    def _focus_lost(self, _event=None):
        if self.visible and self.settings.hide_on_focus_loss:
            self._cancel_timer("_focus_after")
            self._focus_after = self.root.after(100, self._hide_if_unfocused)

    def _hide_if_unfocused(self):
        self._focus_after = None
        if self.visible and not self._suspend_hide and self.root.focus_displayof() is None:
            self.hide_popup()

    def _cancel_timer(self, attribute):
        timer = getattr(self, attribute)
        if timer is not None:
            try:
                self.root.after_cancel(timer)
            except tk.TclError:
                pass
            setattr(self, attribute, None)

    def focus_search(self, _event=None):
        if not self.visible:
            self.show_popup()
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")
        return "break"

    def _focus_results(self, _event=None):
        children = self.tree.get_children()
        if children:
            if not self.tree.selection():
                self.tree.selection_set(children[0])
            self.tree.focus(self.tree.selection()[0])
            self.tree.focus_set()
        return "break"

    def _move_selection(self, step: int):
        children = self.tree.get_children()
        if not children:
            return "break"
        selection = self.tree.selection()
        try:
            index = children.index(selection[0]) if selection else (-1 if step > 0 else 0)
        except ValueError:
            index = -1
        target = children[(index + step) % len(children)]
        self.tree.selection_set(target)
        self.tree.focus(target)
        self.tree.see(target)
        return "break"

    def clear_query(self):
        self.query_var.set("")
        self.focus_search()
        return "break"

    # ---- Kip sistemi ----------------------------------------------------

    def set_mode(self, mode: str, *, schedule: bool = True):
        if mode not in MODE_ORDER:
            mode = MODE_ALL
        self._mode = mode
        self.mode_var.set(mode)
        if hasattr(self, "mode_chip"):
            self.mode_chip.configure(text=mode)
        if self.visible:
            if self.query_var.get().strip() or self._show_rows_when_empty():
                self.table_box.grid()
            else:
                self.table_box.grid_remove()
        if schedule and not self._closing:
            self._schedule_search(0)
        return "break"

    def cycle_mode(self, _event=None):
        try:
            index = MODE_ORDER.index(self._mode)
        except ValueError:
            index = 0
        return self.set_mode(MODE_ORDER[(index + 1) % len(MODE_ORDER)])

    # ---- Arama akışı ----------------------------------------------------

    def _query_changed(self, *_args):
        self._last_typing = time.monotonic()
        if self.query_var.get():
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=5, rely=0.5, anchor="w")
        if self.visible:
            if self.query_var.get().strip() or self._show_rows_when_empty():
                self.table_box.grid()
                self._result_rows = max(1, self._result_rows)
            else:
                self.table_box.grid_remove()
                self._result_rows = 0
            self._position_popup()
        self._schedule_search(120)

    def _schedule_search(self, delay=120):
        if self._closing:
            return
        self._search_generation += 1
        self._pending_open_generation = None
        if self._search_cancel:
            self._search_cancel.set()
        if self._search_future:
            self._search_future.cancel()
        self._cancel_timer("_search_after")
        self._search_after = self.root.after(delay, self._begin_search)

    @staticmethod
    def _file_item(item: FileResult) -> ResultItem:
        return ResultItem(f"file:{item.id}", item.name, item.parent, item.kind, item.path, item.extension)

    def _settings_result(self, text: str) -> tuple[ResultItem, ...]:
        terms = tuple(part for part in fold_text(text).split() if part)
        key = fold_text("DosyaBul ayarlar ayar rofi settings seçenekler kısayol")
        if terms and all(term in key for term in terms):
            return (ResultItem("settings", "DosyaBul Ayarları", "Ctrl + ,", "settings", ""),)
        return ()

    def _search_apps(self, text: str, limit: int) -> tuple[ResultItem, ...]:
        if not self.settings.search_apps:
            return ()
        return tuple(
            ResultItem(app.key, app.name, app.detail, "app:" + app.launch_kind, app.target)
            for app in self.applications.search(text, limit=limit)
        )

    def _search_windows(self, text: str, limit: int) -> tuple[ResultItem, ...]:
        if not self.settings.search_windows:
            return ()
        terms = tuple(part for part in fold_text(text).split() if part)
        found = []
        for window in window_tools.list_windows():
            haystack = fold_text(window.title)
            if all(term in haystack for term in terms):
                found.append(window)
            if len(found) >= limit:
                break
        found.sort(key=lambda window: len(window.title))
        return tuple(
            ResultItem(f"window:{window.handle}", window.title, f"Pencere · {window.pid}", "window", str(window.handle))
            for window in found[:limit]
        )

    def _search_files(self, parsed, limit: int, cancel: threading.Event) -> SearchResults:
        if not self.settings.search_files:
            return SearchResults((), 0, 0, limit)
        return self.database.search(parsed, limit=max(1, limit), cancel=cancel)

    def _search_all(self, parsed, text: str, cancel: threading.Event) -> LauncherResults:
        settings_items = self._settings_result(text)
        application_items = self._search_apps(text, 30)
        window_items = self._search_windows(text, 30)
        reserved = len(settings_items) + len(application_items) + len(window_items)
        files = self._search_files(parsed, MAX_RESULTS - reserved, cancel)
        items = settings_items + application_items + window_items + tuple(self._file_item(item) for item in files.files)
        total = len(settings_items) + len(application_items) + len(window_items) + files.total
        return LauncherResults(items[:MAX_RESULTS], total)

    def _search_scope(self, text: str, parsed, cancel: threading.Event | None = None) -> LauncherResults:
        """Aktif kipe göre yalnızca ilgili kaynakları arar."""
        if self._mode == MODE_FILES:
            files = self._search_files(parsed, MAX_RESULTS, cancel or threading.Event())
            return LauncherResults(tuple(self._file_item(item) for item in files.files), files.total)
        if self._mode == MODE_APPS:
            return LauncherResults(self._search_apps(text, MAX_RESULTS), 0)
        if self._mode == MODE_WINDOWS:
            return LauncherResults(self._search_windows(text, MAX_RESULTS), 0)
        return LauncherResults((), 0)

    def _begin_search(self):
        self._search_after = None
        if self._closing:
            return
        text = self.query_var.get().strip()
        if not text:
            self._pending_open_generation = None
            if self._mode == MODE_WINDOWS:
                windows = self._search_windows("", MAX_RESULTS)
                self.render_results(LauncherResults(windows, len(windows)))
                self._last_results_generation = self._search_generation
                return
            if self._mode == MODE_APPS:
                self.render_results(LauncherResults((), 0))
                self._result_rows = 1
                self._show_empty("Uygulama adı yaz")
                if self.visible:
                    self._position_popup()
                return
            self.render_results(SearchResults((), 0, 0, MAX_RESULTS))
            return
        if text.startswith("/") and self._mode in (MODE_ALL, MODE_COMMANDS) and self.settings.search_commands:
            command = text[1:].strip()
            if command:
                results = LauncherResults((ResultItem("command", command, "Terminalde çalıştır", "command", command),), 1)
                self.render_results(results)
                self._last_results_generation = self._search_generation
                if self._pending_open_generation == self._search_generation:
                    self._pending_open_generation = None
                    self.open_selected()
            else:
                self.render_results(LauncherResults((), 0))
                self._result_rows = 1
                self._show_empty("Komutu / işaretinden sonra yaz · Örnek: /oc")
                if self.visible:
                    self._position_popup()
            return
        if text.startswith("!") and self._mode in (MODE_ALL, MODE_WEB):
            web_text = text[1:].strip()
            if web_text:
                target = resolve_web_input(web_text, self.settings.search_engine)
                results = LauncherResults((ResultItem("web", target.text, target.detail, "web", target.url),), 1)
                self.render_results(results)
                self._last_results_generation = self._search_generation
                if self._pending_open_generation == self._search_generation:
                    self._pending_open_generation = None
                    self.open_selected()
            else:
                self.render_results(LauncherResults((), 0))
                self._result_rows = 1
                self._show_empty("Web araması veya adres yaz · Örnek: !youtube")
                if self.visible:
                    self._position_popup()
            return
        if self._mode == MODE_WEB:
            try:
                target = resolve_web_input(text, self.settings.search_engine)
            except ValueError:
                self.render_results(LauncherResults((), 0))
                return
            results = LauncherResults((ResultItem("web", target.text, target.detail, "web", target.url),), 1)
            self.render_results(results)
            self._last_results_generation = self._search_generation
            if self._pending_open_generation == self._search_generation:
                self._pending_open_generation = None
                self.open_selected()
            return
        if self._mode == MODE_COMMANDS:
            results = LauncherResults((ResultItem("command", text, "Terminalde çalıştır", "command", text),), 1)
            self.render_results(results)
            self._last_results_generation = self._search_generation
            if self._pending_open_generation == self._search_generation:
                self._pending_open_generation = None
                self.open_selected()
            return
        if self._mode == MODE_FILES:
            generation = self._search_generation
            cancel = threading.Event()
            self._search_cancel = cancel
            parsed = parse_plain_query(text)
            future = self.executor.submit(self._search_scope, text, parsed, cancel)
            self._search_future = future

            def complete_files(completed):
                try:
                    results = completed.result()
                except (CancelledError, SearchCancelled):
                    return
                except Exception as error:
                    self.events.put(("search", generation, None, error))
                else:
                    self.events.put(("search", generation, results, None))

            future.add_done_callback(complete_files)
            return
        if self._mode in (MODE_APPS, MODE_WINDOWS):
            try:
                scoped = self._search_scope(text, ())
            except Exception as error:
                self.render_results(LauncherResults((), 0))
                self._show_empty(f"Arama tamamlanamadı: {error}")
                return
            self.render_results(scoped)
            self._last_results_generation = self._search_generation
            if self._pending_open_generation == self._search_generation:
                self._pending_open_generation = None
                self.open_selected()
            return
        try:
            parsed = parse_plain_query(text)
        except QueryError as error:
            self._pending_open_generation = None
            self.render_results(SearchResults((), 0, 0, MAX_RESULTS))
            self._show_empty(str(error))
            return
        generation = self._search_generation
        cancel = threading.Event()
        self._search_cancel = cancel
        future = self.executor.submit(self._search_all, parsed, text, cancel)
        self._search_future = future

        def complete(completed):
            try:
                results = completed.result()
            except (CancelledError, SearchCancelled):
                return
            except Exception as error:
                self.events.put(("search", generation, None, error))
            else:
                self.events.put(("search", generation, results, None))

        future.add_done_callback(complete)

    def _open_search_result(self, _event=None):
        if self._last_results_generation == self._search_generation and self._search_after is None:
            return self.open_selected()
        self._pending_open_generation = self._search_generation
        if self._search_after is not None:
            self._cancel_timer("_search_after")
            self._begin_search()
        elif self._search_future is None or self._search_future.cancelled():
            self._begin_search()
        return "break"

    # ---- Sonuç listesi --------------------------------------------------

    def render_results(self, results: SearchResults | LauncherResults):
        if isinstance(results, SearchResults):
            normalized = LauncherResults(tuple(self._file_item(item) for item in results.files), results.total)
        else:
            normalized = results
        selected = self.tree.selection()
        selected_id = selected[0] if selected else None
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)
        self.items = {item.key: item for item in normalized.items}
        for item in normalized.items:
            self.tree.insert("", "end", iid=item.key, text=item.name, image=self._icon_for(item), tags=(item.kind,))
        if normalized.items:
            self._result_rows = min(self.settings.visible_rows, len(normalized.items))
            self.empty_label.place_forget()
            selected_id = selected_id if selected_id in self.items else normalized.items[0].key
            self.tree.selection_set(selected_id)
            self.tree.focus(selected_id)
        elif not self.query_var.get().strip():
            self._result_rows = 1 if self._show_rows_when_empty() else 0
            self._show_empty(MODE_HINTS.get(self._mode, "Aramak için yazmaya başla"))
        elif self._scanning:
            self._result_rows = 1
            self._show_empty("Henüz eşleşme yok. İlk tarama arka planda sürüyor…")
        else:
            self._result_rows = 1
            self._show_empty("Sonuç bulunamadı.")
        self._selection_changed()
        if self.visible:
            if self.query_var.get().strip() or self._show_rows_when_empty():
                self.table_box.grid()
            else:
                self.table_box.grid_remove()
            self._position_popup()

    def _icon_for(self, item: ResultItem):
        if item.kind.startswith("app:"):
            return self._app_row_icon(item.target)
        if item.kind == "directory":
            return self._folder_icon
        if item.kind == "command":
            return self._terminal_icon
        if item.kind == "settings":
            return self._settings_icon
        if item.kind == "web":
            return self._web_icon
        if item.kind == "window":
            return self._window_icon
        return self._file_icon

    def _app_row_icon(self, target):
        """Uygulama için gerçek logoyu dener; bulamazsa genel uygulama ikonuna düşer."""
        if target and os.path.isfile(target):
            image = self._load_app_icon(target)
            if image is not None:
                return image
        return self._app_icon

    def _show_empty(self, text):
        self.empty_label.configure(text=text)
        self.empty_label.place(relx=0.5, rely=0.5, anchor="center")

    def _selected_item(self) -> ResultItem | None:
        selection = self.tree.selection()
        return self.items.get(selection[0]) if selection else None

    def _selection_changed(self, _event=None):
        item = self._selected_item()
        self.selected_path_var.set(item.path if item else "")

    def _double_click(self, event):
        row = self.tree.identify_row(event.y)
        if row and self.tree.identify_region(event.x, event.y) in {"cell", "tree"}:
            self.tree.selection_set(row)
            self.open_selected()

    def _context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self._suspend_hide = True
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()
                self._suspend_hide = False

    # ---- Eylemler -------------------------------------------------------

    def open_selected(self):
        item = self._selected_item()
        if not item:
            return "break"
        if item.kind == "settings":
            self.open_settings()
            return "break"
        if item.kind == "command":
            try:
                self.hide_popup()
                launch_terminal_command(item.target, self.settings.terminal_directory, self.settings.terminal_application)
            except (OSError, ValueError) as error:
                self.show_popup()
                messagebox.showerror("Komut çalıştırılamadı", str(error), parent=self.root)
            return "break"
        if item.kind == "web":
            try:
                self.hide_popup()
                if not open_web(item.target):
                    raise OSError("Varsayılan web tarayıcısı açılamadı.")
            except OSError as error:
                self.show_popup()
                messagebox.showerror("Web sayfası açılamadı", str(error), parent=self.root)
            return "break"
        if item.kind == "window":
            try:
                handle = int(item.target)
            except (TypeError, ValueError):
                handle = 0
            if handle:
                self.hide_popup()
                window_tools.focus_window(handle)
            return "break"
        if item.kind.startswith("app:"):
            try:
                self.hide_popup()
                launch_application(item)
            except OSError as error:
                self.show_popup()
                messagebox.showerror("Uygulama açılamadı", str(error), parent=self.root)
            return "break"
        if self._needs_confirmation(item):
            self._suspend_hide = True
            try:
                if not messagebox.askyesno("Çalıştırılabilir dosya", f"{item.name}\n\nBu dosya program veya betik çalıştırabilir. Yalnızca kaynağına güveniyorsan aç.\n\nAçılsın mı?", parent=self.root, default="no"):
                    return "break"
            finally:
                self._suspend_hide = False
        try:
            self.hide_popup()
            actions.open_item(item.path)
        except OSError as error:
            self.show_popup()
            messagebox.showerror("Öğe açılamadı", str(error), parent=self.root)
        return "break"

    def _needs_confirmation(self, item: ResultItem) -> bool:
        if not self.settings.confirm_executables:
            return False
        if item.kind != "file":
            return False
        return Path(item.path).suffix.casefold().lstrip(".") in actions.EXECUTABLE_EXTENSIONS and os.path.isfile(item.path)

    def reveal_selected(self):
        item = self._selected_item()
        if item and item.kind in {"file", "directory"}:
            try:
                self.hide_popup()
                actions.reveal_file(item.path)
            except OSError as error:
                self.show_popup()
                messagebox.showerror("Konum açılamadı", str(error), parent=self.root)
        return "break"

    def copy_selected(self):
        item = self._selected_item()
        if item:
            self.root.clipboard_clear()
            self.root.clipboard_append(item.path)
            self.status_var.set("Yol kopyalandı.")
            self._cancel_timer("_toast_after")
            self._toast_after = self.root.after(2000, self._clear_toast)
        return "break"

    def _clear_toast(self):
        self._toast_after = None
        self.status_var.set(self._idle_status)

    # ---- Kısayol --------------------------------------------------------

    def _rebind_hotkey(self, spec: HotkeySpec) -> tuple[bool, str | None]:
        spec = spec.normalized()
        if not self._hotkey_enabled or (self._hotkey and spec == self._hotkey.spec):
            return True, None
        candidate = HotkeyService(lambda: self.events.put(("toggle",)), spec=spec)
        if candidate.start():
            previous = self._hotkey
            self._hotkey = candidate
            self.hotkey_available = True
            if previous:
                previous.stop()
            return True, None
        error = str(candidate.error or "Kısayol kaydedilemedi.")
        candidate.stop()
        return False, error

    # ---- Ayarlar penceresi ---------------------------------------------

    def open_settings(self, _event=None):
        if self._settings_window and self._settings_window.winfo_exists():
            self._settings_window.deiconify()
            self._settings_window.lift()
            self._settings_window.focus_force()
            return "break"
        theme = self._palette()
        self._suspend_hide = True
        window = tk.Toplevel(self.root)
        self._settings_window = window
        window.title("DosyaBul Ayarları")
        window.configure(bg=theme.background)
        window.resizable(False, False)
        window.transient(self.root)

        hotkey_var = tk.StringVar(value=self.settings.hotkey)
        hotkey_hint_var = tk.StringVar(value="Alana tıkla, ardından istediğin tuş birleşimine bas.")
        self._settings_hotkey_spec = self.settings.hotkey_spec
        rows_var = tk.StringVar(value=str(self.settings.visible_rows))
        opacity_var = tk.IntVar(value=self.settings.opacity)
        width_var = tk.IntVar(value=self.settings.panel_width)
        position_var = tk.StringVar(value=self.settings.panel_position)
        monitor_var = tk.StringVar(value=self.settings.monitor_mode)
        engine_var = tk.StringVar(value=self.settings.search_engine)
        theme_var = tk.StringVar(value=self.settings.theme)
        accent_var = tk.StringVar(value=self.settings.accent_color)
        mode_var = tk.StringVar(value=self.settings.default_mode)
        terminal_var = tk.StringVar(value=self.settings.terminal_application)
        size_var = tk.IntVar(value=self.settings.font_size)
        rowscale_var = tk.IntVar(value=self.settings.row_scale)
        hide_var = tk.BooleanVar(value=self.settings.hide_on_focus_loss)
        refresh_var = tk.BooleanVar(value=self.settings.refresh_on_start)
        files_var = tk.BooleanVar(value=self.settings.search_files)
        apps_var = tk.BooleanVar(value=self.settings.search_apps)
        commands_var = tk.BooleanVar(value=self.settings.search_commands)
        windows_var = tk.BooleanVar(value=self.settings.search_windows)
        confirm_var = tk.BooleanVar(value=self.settings.confirm_executables)
        tray_var = tk.BooleanVar(value=self.settings.minimize_to_tray)
        startup_was_enabled = is_startup_enabled()
        startup_var = tk.BooleanVar(value=startup_was_enabled)
        show_startup_var = tk.BooleanVar(value=self.settings.show_on_startup)
        directory_var = tk.StringVar(value=self.settings.terminal_directory)

        content = tk.Frame(window, bg=theme.background)
        content.pack(fill="both", expand=True, padx=18, pady=12)
        tk.Label(content, text="Rofi ayarları", bg=theme.background, fg=theme.text, font=(FONT_FAMILY, 17, "bold"), anchor="w").grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        content.columnconfigure(1, weight=1)

        def label(row, text):
            tk.Label(content, text=text, bg=theme.background, fg=theme.text, font=(FONT_FAMILY, 10), anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 14), pady=3)

        row = 1
        label(row, "Genel kısayol")
        hotkey_button = tk.Button(content, textvariable=hotkey_var, bg=theme.surface, fg=theme.text, activebackground=theme.surface, activeforeground=theme.text, highlightbackground=theme.border, highlightthickness=1, relief="flat", font=(FONT_FAMILY, 10), anchor="w", padx=10, pady=7, takefocus=True)
        hotkey_button.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(3, 1))
        row += 1
        hotkey_hint = tk.Label(content, textvariable=hotkey_hint_var, bg=theme.background, fg=theme.muted, font=(FONT_FAMILY, 8), anchor="w")
        hotkey_hint.grid(row=row, column=1, columnspan=2, sticky="ew", pady=(0, 3))
        row += 1

        def begin_hotkey_capture():
            hotkey_var.set("Yeni kısayola bas…")
            hotkey_hint_var.set("Win, Ctrl, Alt veya Shift ile birlikte bir tuşa bas.")
            hotkey_button.focus_set()

        def record_hotkey(event):
            try:
                captured = captured_hotkey(event)
            except ValueError as error:
                hotkey_hint_var.set(str(error))
                return "break"
            if captured is None:
                return "break"
            self._settings_hotkey_spec = captured
            hotkey_var.set(format_hotkey(captured))
            if captured.modifiers == MOD_WIN and captured.key == VK_SPACE:
                hotkey_hint_var.set("Win+Space Windows dil değiştiricisine ayrılmış; kaydetme başarısız olabilir.")
            else:
                hotkey_hint_var.set("Kısayol yakalandı; Kaydet ile etkinleştir.")
            return "break"

        hotkey_button.configure(command=begin_hotkey_capture)
        hotkey_button.bind("<KeyPress>", record_hotkey)

        label(row, "Görünür sonuç")
        rows_combo = ttk.Combobox(content, textvariable=rows_var, values=tuple(map(str, ROW_CHOICES)), state="readonly", style="Settings.TCombobox", width=8)
        rows_combo.grid(row=row, column=1, sticky="w", pady=3)
        row += 1
        label(row, "Panel genişliği")
        tk.Scale(content, variable=width_var, from_=320, to=800, resolution=20, orient="horizontal", bg=theme.background, fg=theme.text, troughcolor=theme.surface, activebackground=theme.accent, highlightthickness=0, showvalue=True, length=230, font=(FONT_FAMILY, 9)).grid(row=row, column=1, columnspan=2, sticky="ew", pady=1)
        row += 1
        label(row, "Panel konumu")
        ttk.Combobox(content, textvariable=position_var, values=POSITION_CHOICES, state="readonly", style="Settings.TCombobox", width=18).grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        row += 1
        label(row, "Ekran")
        ttk.Combobox(content, textvariable=monitor_var, values=MONITOR_CHOICES, state="readonly", style="Settings.TCombobox", width=24).grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        row += 1
        label(row, "Açılış kipi")
        ttk.Combobox(content, textvariable=mode_var, values=MODE_CHOICES, state="readonly", style="Settings.TCombobox", width=18).grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        row += 1
        label(row, "Tema")
        ttk.Combobox(content, textvariable=theme_var, values=THEME_CHOICES, state="readonly", style="Settings.TCombobox", width=18).grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        row += 1
        label(row, "Vurgu rengi")
        accent_box = tk.Frame(content, bg=theme.background)
        accent_box.grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        swatch_holder = tk.Frame(accent_box, bg=theme.surface, highlightbackground=theme.border, highlightthickness=1)
        swatch_holder.pack(side="left", padx=(0, 6))
        swatch = tk.Label(swatch_holder, text="  ", bg=theme.accent, width=3)
        swatch.pack()
        accent_entry = tk.Entry(accent_box, textvariable=accent_var, bg=theme.surface, fg=theme.text, insertbackground=theme.text, relief="flat", width=10, font=(FONT_FAMILY, 9))
        accent_entry.pack(side="left", ipady=4)

        def preview_accent(*_args):
            color = accent_var.get().strip()
            if color and not color.startswith("#"):
                color = "#" + color
            if len(color) == 7:
                try:
                    swatch.configure(bg=color)
                except tk.TclError:
                    pass

        accent_var.trace_add("write", preview_accent)
        presets_box = tk.Frame(content, bg=theme.background)
        presets_box.grid(row=row + 1, column=0, columnspan=3, sticky="w", pady=(0, 4), padx=(0, 0))
        for preset_name, preset_color in themes.ACCENT_PRESETS:
            button = tk.Button(presets_box, text="", bg=preset_color, width=2, relief="flat", command=lambda c=preset_color: accent_var.set(c))
            button.pack(side="left", padx=(0, 4))
        tk.Button(presets_box, text="Tema rengi", bg=theme.surface, fg=theme.text, relief="flat", padx=8, command=lambda: accent_var.set("")).pack(side="left", padx=(6, 0))
        row += 2
        label(row, "Saydamlık")
        tk.Scale(content, variable=opacity_var, from_=85, to=100, orient="horizontal", bg=theme.background, fg=theme.text, troughcolor=theme.surface, activebackground=theme.accent, highlightthickness=0, showvalue=True, length=230, font=(FONT_FAMILY, 9)).grid(row=row, column=1, columnspan=2, sticky="ew", pady=1)
        row += 1
        label(row, "Yazı boyutu")
        tk.Scale(content, variable=size_var, from_=9, to=24, orient="horizontal", bg=theme.background, fg=theme.text, troughcolor=theme.surface, activebackground=theme.accent, highlightthickness=0, showvalue=True, length=230, font=(FONT_FAMILY, 9)).grid(row=row, column=1, columnspan=2, sticky="ew", pady=1)
        row += 1
        label(row, "Satır yüksekliği")
        tk.Scale(content, variable=rowscale_var, from_=80, to=200, resolution=2, orient="horizontal", bg=theme.background, fg=theme.text, troughcolor=theme.surface, activebackground=theme.accent, highlightthickness=0, showvalue=True, length=230, font=(FONT_FAMILY, 9)).grid(row=row, column=1, columnspan=2, sticky="ew", pady=1)
        row += 1
        label(row, "Web araması")
        ttk.Combobox(content, textvariable=engine_var, values=tuple(SEARCH_ENGINES), state="readonly", style="Settings.TCombobox", width=18).grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        row += 1
        label(row, "Terminal")
        ttk.Combobox(content, textvariable=terminal_var, values=TERMINAL_CHOICES, state="readonly", style="Settings.TCombobox", width=18).grid(row=row, column=1, columnspan=2, sticky="ew", pady=3)
        row += 1
        label(row, "Komut klasörü")
        directory_entry = tk.Entry(content, textvariable=directory_var, bg=theme.surface, fg=theme.text, insertbackground=theme.text, relief="flat", font=(FONT_FAMILY, 9))
        directory_entry.grid(row=row, column=1, sticky="ew", ipady=5, pady=3)

        def choose_directory():
            selected = filedialog.askdirectory(initialdir=directory_var.get(), parent=window, title="Terminal komutlarının çalışma klasörü")
            if selected:
                directory_var.set(selected)

        tk.Button(content, text="…", command=choose_directory, bg=theme.surface, fg=theme.text, activebackground=theme.accent, relief="flat", padx=10, pady=3).grid(row=row, column=2, padx=(7, 0), pady=3)
        row += 1

        checks = tk.Frame(content, bg=theme.background)
        checks.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 2))
        row += 1

        def check(text, variable, row_index, column):
            tk.Checkbutton(checks, text=text, variable=variable, bg=theme.background, fg=theme.text, activebackground=theme.background, activeforeground=theme.text, selectcolor=theme.surface, font=(FONT_FAMILY, 9), anchor="w").grid(row=row_index, column=column, sticky="w", padx=(0, 22), pady=2)

        check("Uygulamaları ara", apps_var, 0, 0)
        check("Dosya ve klasörleri ara", files_var, 0, 1)
        check("Komut çalıştır", commands_var, 1, 0)
        check("Açık pencereleri ara", windows_var, 1, 1)
        check("Dışarı tıklayınca gizle", hide_var, 2, 0)
        check("Açılışta dosya indeksini yenile", refresh_var, 2, 1)
        check("Windows ile başlat", startup_var, 3, 0)
        check("Başlangıçta paneli göster", show_startup_var, 3, 1)
        check("Çalıştırılabilir dosyada onay iste", confirm_var, 4, 0)
        check("Kapatınca sistem tepsisine küçült", tray_var, 4, 1)

        tk.Label(content, text="Web: !arama / !site.com   ·   Komut: /komut   ·   Kip: Ctrl+K veya Tab", bg=theme.background, fg=theme.muted, font=(FONT_FAMILY, 9), anchor="w").grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        row += 1
        actions_box = tk.Frame(content, bg=theme.background)
        actions_box.grid(row=row, column=0, columnspan=3, sticky="e", pady=(3, 0))

        def close_dialog():
            self._suspend_hide = False
            if window.winfo_exists():
                window.destroy()
            self._settings_window = None
            self._settings_hotkey_spec = None
            if self.visible:
                self.focus_search()

        def save_settings():
            if not files_var.get() and not apps_var.get() and not windows_var.get() and not commands_var.get():
                messagebox.showwarning("Arama kaynağı gerekli", "En az bir arama kaynağı açık olmalı.", parent=window)
                return
            if not os.path.isdir(directory_var.get()):
                messagebox.showwarning("Klasör bulunamadı", "Komut çalışma klasörü geçerli değil.", parent=window)
                return
            selected_hotkey = self._settings_hotkey_spec or self.settings.hotkey_spec
            updated = AppSettings(
                hotkey=format_hotkey(selected_hotkey), hotkey_modifiers=selected_hotkey.modifiers, hotkey_key=selected_hotkey.key,
                visible_rows=int(rows_var.get()), opacity=opacity_var.get(), panel_width=width_var.get(),
                panel_position=position_var.get(), monitor_mode=monitor_var.get(), search_engine=engine_var.get(),
                hide_on_focus_loss=hide_var.get(), refresh_on_start=refresh_var.get(),
                show_on_startup=show_startup_var.get(), search_files=files_var.get(), search_apps=apps_var.get(),
                search_commands=commands_var.get(), search_windows=windows_var.get(),
                terminal_application=terminal_var.get(), terminal_directory=directory_var.get(),
                font_size=size_var.get(), row_scale=rowscale_var.get(), theme=theme_var.get(),
                accent_color=accent_var.get(), default_mode=mode_var.get(), confirm_executables=confirm_var.get(),
                minimize_to_tray=tray_var.get(),
            ).normalized()
            changed, error = self._rebind_hotkey(updated.hotkey_spec)
            if not changed:
                messagebox.showerror("Kısayol kullanılamıyor", f"{updated.hotkey} başka bir uygulama tarafından kullanılıyor.\n\n{error}", parent=window)
                return
            try:
                set_startup(startup_var.get(), updated.show_on_startup)
                self.settings = self.settings_store.save(updated)
            except OSError as error:
                self._rebind_hotkey(self.settings.hotkey_spec)
                try:
                    set_startup(startup_was_enabled, self.settings.show_on_startup)
                except OSError:
                    pass
                messagebox.showerror("Ayarlar kaydedilemedi", str(error), parent=window)
                return
            self._apply_settings()
            close_dialog()
            if self.query_var.get().strip() or self._show_rows_when_empty():
                self._schedule_search(0)

        tk.Button(actions_box, text="Vazgeç", command=close_dialog, bg=theme.surface, fg=theme.text, activebackground=theme.surface, relief="flat", padx=14, pady=7).pack(side="left", padx=(0, 8))
        tk.Button(actions_box, text="Kaydet", command=save_settings, bg=theme.accent, fg=theme.accent_text, activebackground=theme.border, relief="flat", padx=16, pady=7).pack(side="left")
        window.protocol("WM_DELETE_WINDOW", close_dialog)
        window.bind("<Escape>", lambda _event: close_dialog())
        window.update_idletasks()
        width, height = 560, window.winfo_reqheight()
        area = active_work_area(self.root)
        x = area.left + (area.width - width) // 2
        y = area.top + max(20, (area.height - height) // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.lift()
        hotkey_button.focus_set()
        return "break"

    def _recolor_widgets(self):
        """Tema degisince kalici widget renklerini yeniler."""
        theme = self._palette()
        self.panel_border.configure(bg=theme.border)
        self.main_frame.configure(bg=theme.background)
        self.search_box.configure(bg=theme.accent)
        self.search_canvas.configure(bg=theme.accent)
        self.search_canvas.itemconfigure(self._search_oval, outline=theme.accent_text)
        self.search_canvas.itemconfigure(self._search_line, fill=theme.accent_text)
        self.entry_box.configure(bg=theme.accent)
        self.search_entry.configure(bg=theme.accent, fg=theme.accent_text, insertbackground=theme.accent_text,
                                    selectbackground=theme.background, selectforeground=theme.accent_text)
        self.placeholder.configure(bg=theme.accent, fg=theme.text)
        self.mode_chip.configure(bg=theme.accent, fg=theme.accent_text)
        self.table_box.configure(bg=theme.background)
        self.empty_label.configure(bg=theme.background, fg=theme.muted)

    def _apply_settings(self):
        self._theme = self._resolve_theme()
        self._icon_cache.clear()
        self._configure_styles()
        self._make_icons()
        self._recolor_widgets()
        self.root.configure(bg=self._theme.background)
        self.root.attributes("-alpha", self.settings.opacity / 100)
        self._idle_status = self._ready_status()
        self.status_var.set(self._idle_status)
        if self.visible:
            if self.query_var.get().strip() or self._show_rows_when_empty():
                self.table_box.grid()
            self._position_popup()

    # ---- Tarama ---------------------------------------------------------

    def _needs_initial_scan(self) -> bool:
        root_count, item_count, _last_scan = self.database.overview()
        return root_count == 0 or item_count == 0

    def _start_application_refresh(self):
        if self._app_thread and self._app_thread.is_alive():
            return

        def work():
            try:
                self.applications.refresh()
            except Exception as error:
                self.events.put(("apps_ready", error))
            else:
                self.events.put(("apps_ready", None))

        self._app_thread = threading.Thread(target=work, daemon=True, name="DosyaBul-Uygulamalar")
        self._app_thread.start()

    def refresh_all(self, _event=None):
        self._start_application_refresh()
        if self.settings.search_files:
            return self.start_scan()
        self._idle_status = "Uygulama listesi yenileniyor…"
        self.status_var.set(self._idle_status)
        return "break"

    def start_scan(self, *, paths=None):
        if self._closing or self._scanning or (self._scan_thread and self._scan_thread.is_alive()):
            return "break"
        self._cancel_timer("_auto_after")
        self._scanning = True
        self._scan_cancel = threading.Event()
        self._last_live_refresh = time.monotonic()
        self._idle_status = "Bilgisayar taranıyor…"
        self.status_var.set(self._idle_status)
        if self.visible:
            self._position_popup()

        def work():
            try:
                detected = tuple(paths) if paths is not None else tuple(self.drive_provider())
                if self._scan_cancel.is_set():
                    return
                roots = self.database.synchronize_drives(detected)
                self.events.put(("roots", tuple(path_key(root.path) for root in roots)))
                report = Indexer(self.database).scan(roots, self._scan_cancel, lambda progress: self.events.put(("progress", progress)))
            except Exception as error:
                self.events.put(("scan_done", None, error))
            else:
                self.events.put(("scan_done", report, None))

        self._scan_thread = threading.Thread(target=work, daemon=True, name="DosyaBul-Tarama")
        self._scan_thread.start()
        return "break"

    def _scan_progress(self, progress: ScanProgress):
        self._idle_status = f"Tarama sürüyor · {format_count(progress.items_seen)} öğe"
        if self._toast_after is None:
            self.status_var.set(self._idle_status)
        now = time.monotonic()
        if self.query_var.get().strip() and now - self._last_live_refresh > 0.7 and now - self._last_typing > 0.4 and self._search_after is None:
            self._last_live_refresh = now
            self._schedule_search(0)

    def _scan_finished(self, report: ScanReport | None, error: Exception | None):
        self._scanning = False
        if error:
            logging.error("Tarama başarısız", exc_info=(type(error), error, error.__traceback__))
            self._idle_status = "Tarama tamamlanamadı. Mevcut sonuçlarda arayabilirsin."
        elif not self._drive_paths:
            self._idle_status = "Aranabilecek sürücü bulunamadı."
        elif report and report.skipped:
            self._idle_status = "Hazır · Erişilemeyen alanlar atlandı."
            logging.warning("Tarama sırasında erişilemeyen öğeler:\n%s", "\n".join(report.errors))
        else:
            self._idle_status = self._ready_status()
        if self._toast_after is None:
            self.status_var.set(self._idle_status)
        if self.visible:
            self._position_popup()
        if self.query_var.get().strip():
            self._schedule_search(0)

    # ---- Olay döngüsü ---------------------------------------------------

    def _drain_events(self):
        if self._closing:
            return
        self._cancel_timer("_event_after")
        if self.activation_checker and self.activation_checker():
            self.show_popup()
        for _ in range(100):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "search":
                _, generation, results, error = event
                if generation != self._search_generation:
                    continue
                if error:
                    self._pending_open_generation = None
                    self._search_future = None
                    logging.error("Arama başarısız", exc_info=(type(error), error, error.__traceback__))
                    self.render_results(SearchResults((), 0, 0, MAX_RESULTS))
                    self._show_empty("Arama tamamlanamadı.")
                else:
                    self.render_results(results)
                    self._last_results_generation = generation
                    if self._pending_open_generation == generation:
                        self._pending_open_generation = None
                        self.open_selected()
            elif event[0] == "roots":
                self._drive_paths = event[1]
            elif event[0] == "progress":
                self._scan_progress(event[1])
            elif event[0] == "scan_done":
                self._scan_finished(event[1], event[2])
            elif event[0] == "apps_ready":
                error = event[1]
                if error:
                    logging.warning("Uygulama listesi yenilenemedi: %s", error)
                else:
                    if not self._scanning:
                        self._idle_status = self._ready_status()
                        if self._toast_after is None:
                            self.status_var.set(self._idle_status)
                    if self.query_var.get().strip() and not self.query_var.get().lstrip().startswith("/"):
                        self._schedule_search(0)
            elif event[0] == "toggle":
                self.toggle_popup()
            elif event[0] == "tray_toggle":
                self.toggle_popup()
            elif event[0] == "tray_menu":
                self._tray_menu()
        self._event_after = self.root.after(50, self._drain_events)

    # ---- Sistem tepsisi -------------------------------------------------

    def setup_tray(self):
        """Sistem tepsisine ikon ekler (destekleniyorsa)."""
        if not self._tray_enabled:
            return False
        if self._tray is not None:
            return self._tray.available
        handle = tray_module.load_tray_icon()
        icon = tray_module.TrayIcon(
            tooltip="DosyaBul",
            on_select=lambda: self.events.put(("tray_toggle",)),
            on_context=lambda: self.events.put(("tray_menu",)),
            icon_handle=handle,
        )
        if icon.start():
            self._tray = icon
            return True
        return False

    def _tray_menu(self):
        """Tepsi ikonuna sag tiklaninca kucuk bir menü acar."""
        if self._closing:
            return
        theme = self._palette()
        menu = tk.Menu(self.root, tearoff=False, font=(FONT_FAMILY, 10))
        menu.add_command(label="Göster / Gizle", command=lambda: self.events.put(("tray_toggle",)))
        menu.add_command(label="Ayarlar", command=self.open_settings)
        menu.add_command(label="Yenile", command=self.refresh_all)
        menu.add_separator()
        menu.add_command(label="Çıkış", command=self.quit_app)
        try:
            self._suspend_hide = True
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()
            self._suspend_hide = False

    def quit_app(self):
        """Tepsiden tamamen çıkar."""
        self._quitting = True
        self.close()

    def _on_window_close(self):
        """Pencere kapatma: ayar açıksa tepsine küçülür, yoksa çıkar."""
        if self.settings.minimize_to_tray and self._tray is not None:
            self.minimize_to_tray()
        else:
            self.quit_app()

    def minimize_to_tray(self):
        """Paneli gizler; tepsi ikonu etkinse uygulama arka planda kalir."""
        self.hide_popup()
        if self._tray is not None:
            self._tray.set_tooltip(f"DosyaBul · {self.settings.hotkey}")

    def close(self):
        if self._closing:
            return
        self._closing = True
        self._shown = False
        self._scan_cancel.set()
        if self._search_cancel:
            self._search_cancel.set()
        for name in ("_search_after", "_event_after", "_auto_after", "_toast_after", "_focus_after"):
            self._cancel_timer(name)
        if self._tray is not None:
            self._tray.stop()
            self._tray = None
        if self._hotkey:
            self._hotkey.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def wait_for_background(self, timeout=2) -> bool:
        self._scan_cancel.set()
        if self._search_cancel:
            self._search_cancel.set()
        if self._scan_thread:
            self._scan_thread.join(timeout)
        if self._app_thread:
            self._app_thread.join(timeout)
        self.executor.shutdown(wait=True, cancel_futures=True)
        return not (self._scan_thread and self._scan_thread.is_alive()) and not (self._app_thread and self._app_thread.is_alive())


def main(argv: list[str] | None = None) -> int:
    """Uygulamayı başlatır; Rofi benzeri panel açar."""
    import argparse

    parser = argparse.ArgumentParser(prog="DosyaBul", description="Rofi tarzı arama paneli")
    parser.add_argument("--background", action="store_true", help="Paneli göstermeden arka planda bekle")
    parser.add_argument("--index", action="store_true", help="Yalnızca dosya indeksini yenile ve çık")
    parser.add_argument("--data-dir", default=None, help="İndeks ve ayarların tutulacağı klasör")
    arguments = parser.parse_args(argv)

    data_dir = Path(arguments.data_dir) if arguments.data_dir else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DosyaBul"
    data_dir.mkdir(parents=True, exist_ok=True)
    actions.configure_windows()
    database = IndexDatabase(data_dir / "index.sqlite3")
    if arguments.index:
        roots = database.synchronize_drives(discover_drives())
        report = Indexer(database).scan(roots, threading.Event())
        logging.info("İndeks güncellendi: %s öğe", format_count(report.added))
        database.close()
        return 0
    from .instance import InstanceGuard
    guard = InstanceGuard(data_dir)
    if not guard.acquired:
        guard.signal_existing()
        database.close()
        return 0
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    root = tk.Tk()
    app = FinderApp(root, database, start_hidden=arguments.background)
    try:
        root.mainloop()
    finally:
        app.wait_for_background()
        database.close()
        guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
