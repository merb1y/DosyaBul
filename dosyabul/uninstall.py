"""Windows kayıt defterinden kurulu programlari bulur ve kaldırıcılarını çalıştırır."""

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .query import fold_text

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


@dataclass(frozen=True)
class InstalledProgram:
    key: str
    name: str
    version: str = ""
    publisher: str = ""
    uninstall_string: str = ""

    @property
    def search_key(self) -> str:
        return fold_text(f"{self.name} {self.publisher}")


def uninstall_roots() -> tuple[tuple[int, str], ...]:
    """Kaldırma kayıtlarının okunacagi (hive, yol) ciftlerini dondurur."""
    if os.name != "nt":
        return ()
    import winreg

    return (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    )


def installed_programs() -> tuple[InstalledProgram, ...]:
    """Kayit defterindeki tum gecerli kaldirma kayitlarini toplar."""
    if os.name != "nt":
        return ()
    import winreg

    programs: dict[str, InstalledProgram] = {}
    for hive, path in uninstall_roots():
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                if subkey_name in programs:
                    continue
                try:
                    with winreg.OpenKey(root, subkey_name) as subkey:
                        values = {}
                        for name in (
                            "DisplayName",
                            "DisplayVersion",
                            "Publisher",
                            "UninstallString",
                            "SystemComponent",
                        ):
                            try:
                                values[name] = winreg.QueryValueEx(subkey, name)[0]
                            except OSError:
                                pass
                except OSError:
                    continue
                display_name = str(values.get("DisplayName") or "").strip()
                uninstall_string = str(values.get("UninstallString") or "").strip()
                if not display_name or not uninstall_string:
                    continue
                # Yama ve sistem bilesenleri kaldirilabilir program degildir.
                if str(values.get("SystemComponent") or "0").strip() == "1":
                    continue
                if display_name.casefold().startswith("kb"):
                    continue
                programs[subkey_name] = InstalledProgram(
                    key=subkey_name,
                    name=display_name,
                    version=str(values.get("DisplayVersion") or "").strip(),
                    publisher=str(values.get("Publisher") or "").strip(),
                    uninstall_string=uninstall_string,
                )
    return tuple(programs.values())


def search_installed_programs(query: str, programs: tuple[InstalledProgram, ...] | None = None) -> tuple[InstalledProgram, ...]:
    """Program adina gore kurulu programlari siralar; tam eslesme basta olur."""
    query = (query or "").strip()
    if not query:
        return ()
    terms = tuple(part for part in fold_text(query).split() if part)
    if not terms:
        return ()
    if programs is None:
        programs = installed_programs()
    matches = []
    for program in programs:
        key = program.search_key
        if not all(term in key for term in terms):
            continue
        name = fold_text(program.name)
        if name == fold_text(query):
            rank = (0, name)
        elif name.startswith(fold_text(query)):
            rank = (1, name)
        else:
            rank = (2, name)
        matches.append((rank, program))
    matches.sort(key=lambda pair: pair[0])
    return tuple(program for _, program in matches[:10])


def launch_uninstall(uninstall_string: str) -> None:
    """Kayit defterindeki kaldirma komutunu calistirir (sihirbazi UI olarak acar)."""
    string = (uninstall_string or "").strip()
    if not string:
        raise ValueError("Kaldırma komutu boş.")
    try:
        parts = shlex.split(string, posix=False)
    except ValueError:
        parts = []
    if parts:
        executable = parts[0].strip('"').strip()
        arguments = [part.strip('"') for part in parts[1:]]
        if executable and Path(executable).is_file():
            subprocess.Popen([executable, *arguments], creationflags=CREATE_NO_WINDOW)
            return
    # Yolu tirsiz/bozuk kayitlar icin cmd uzerinden dene.
    subprocess.Popen(string, shell=True, creationflags=CREATE_NO_WINDOW)
