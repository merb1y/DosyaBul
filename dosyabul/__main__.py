import argparse
import logging
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from . import __version__
from .actions import configure_windows
from .app import FinderApp
from .database import IndexDatabase
from .instance import InstanceGuard


class TurkishHelpFormatter(argparse.HelpFormatter):
    def _format_usage(self, usage, actions, groups, prefix):
        return super()._format_usage(usage, actions, groups, prefix or "Kullanım: ")


def default_data_directory() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "DosyaBul"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "DosyaBul"


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="DosyaBul", description="Windows için Rofi tarzı uygulama, komut ve dosya arama.", usage="%(prog)s [--background] [--data-dir KLASÖR] [--version]", add_help=False, formatter_class=TurkishHelpFormatter)
    parser._optionals.title = "Seçenekler"
    parser.add_argument("-h", "--help", action="help", help="Bu yardım metnini göster.")
    parser.add_argument("--data-dir", type=Path, metavar="KLASÖR", help="İndeksi ve günlükleri bu klasörde sakla.")
    parser.add_argument("--version", action="version", version=f"DosyaBul {__version__}", help="Sürüm bilgisini göster.")
    parser.add_argument("--background", action="store_true", help="Arka planda başlat; ayarlanan kısayolla göster.")
    parser.add_argument("--test-drive", type=Path, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    data_directory = arguments.data_dir or default_data_directory()
    window = None
    instance = None
    application = None
    try:
        data_directory.mkdir(parents=True, exist_ok=True)
        instance = InstanceGuard(data_directory)
        configure_windows()
        if not instance.acquired:
            # Otomatik başlangıç ikinci kez tetiklense bile paneli açma.
            # Yalnızca elle yapılan açılış mevcut pencereyi öne getirir.
            if not arguments.background:
                instance.signal_existing()
            return 0
        logging.basicConfig(filename=data_directory / "dosyabul.log", level=logging.WARNING, encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s", force=True)
        database = IndexDatabase(data_directory / "index.sqlite3")
        window = tk.Tk()
        window.withdraw()  # Çerçevesiz panel hazırlanırken ekranda parlamasın.
        icon_path = resource_path("assets/icon.png")
        if icon_path.exists():
            icon = tk.PhotoImage(file=str(icon_path))
            window.iconphoto(True, icon)
        if arguments.test_drive is not None:
            application = FinderApp(window, database, drive_provider=lambda: (arguments.test_drive.absolute(),), start_hidden=arguments.background, activation_checker=instance.activation_requested)
        else:
            application = FinderApp(window, database, start_hidden=arguments.background, activation_checker=instance.activation_requested)
        window.report_callback_exception = lambda kind, value, traceback: _report_ui_error(window, kind, value, traceback)
        window.mainloop()
        return 0
    except Exception as error:
        logging.exception("Uygulama başlatılamadı")
        try:
            if window is None:
                window = tk.Tk()
                window.withdraw()
            messagebox.showerror("DosyaBul başlatılamadı", f"{error}\n\nİndeks klasörü: {data_directory}\nKlasörün yazılabilir olduğunu kontrol et. Ayrıntılar dosyabul.log dosyasında.", parent=window)
            window.destroy()
        except tk.TclError:
            print(f"DosyaBul başlatılamadı: {error}", file=sys.stderr)
        return 1
    finally:
        finished = application.wait_for_background() if application is not None else True
        if instance is not None and finished:
            instance.close()
        # Engellenmiş bir ağ taraması varsa mutex, süreç bittiğinde Windows tarafından bırakılır.


def _report_ui_error(window, kind, value, traceback):
    logging.error("Arayüz hatası", exc_info=(kind, value, traceback))
    messagebox.showerror("İşlem tamamlanamadı", f"{value}\n\nAyrıntılar yerel dosyabul.log dosyasına kaydedildi.", parent=window)


if __name__ == "__main__":
    raise SystemExit(main())
