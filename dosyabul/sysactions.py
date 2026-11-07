"""Sistem komutları (kilitle, uyku, kapat...). Yıkıcı olanlar onay ister."""

import os
import subprocess
from dataclasses import dataclass

from .query import fold_text

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


@dataclass(frozen=True)
class SystemAction:
    id: str
    name: str
    keywords: str
    command: tuple[str, ...] = ()
    uri: str = ""
    confirm: bool = False


ACTIONS = (
    SystemAction("lock", "Ekranı kilitle", "kilitle lock", ("rundll32.exe", "user32.dll,LockWorkStation")),
    SystemAction("sleep", "Uyku", "uyku sleep suspend", ("rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"), confirm=True),
    SystemAction("hibernate", "Hazırda beklet", "hazirda beklet hibernate", ("shutdown.exe", "/h"), confirm=True),
    SystemAction("signout", "Oturumu kapat", "oturum kapat cikis logout sign out", ("shutdown.exe", "/l"), confirm=True),
    SystemAction("restart", "Yeniden başlat", "yeniden baslat restart reboot", ("shutdown.exe", "/r", "/t", "0"), confirm=True),
    SystemAction("shutdown", "Bilgisayarı kapat", "kapat shutdown power off", ("shutdown.exe", "/s", "/t", "0"), confirm=True),
    SystemAction("wifi", "Wi-Fi ayarları", "wifi wi-fi kablosuz ag network", uri="ms-settings:network-wifi"),
    SystemAction("bluetooth", "Bluetooth ayarları", "bluetooth", uri="ms-settings:bluetooth"),
    SystemAction("sound", "Ses ayarları", "ses sound volume", uri="ms-settings:sound"),
    SystemAction("display", "Ekran ayarları", "ekran display monitor", uri="ms-settings:display"),
    SystemAction("battery", "Pil ve güç ayarları", "pil guc battery power", uri="ms-settings:batterysaver"),
    SystemAction("screenshot", "Ekran görüntüsü al", "ekran goruntusu screenshot snip", uri="ms-screenclip:"),
    SystemAction("taskmgr", "Görev yöneticisi", "gorev yoneticisi task manager", ("taskmgr.exe",)),
    SystemAction(
        "recyclebin", "Geri dönüşüm kutusunu boşalt", "geri donusum cop recycle bin empty",
        ("powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"),
        confirm=True,
    ),
)
_BY_ID = {action.id: action for action in ACTIONS}


def get_action(action_id: str) -> SystemAction | None:
    return _BY_ID.get(action_id)


def search_actions(text: str) -> tuple[SystemAction, ...]:
    terms = tuple(part for part in fold_text(text).split() if part)
    return tuple(
        action for action in ACTIONS
        if all(term in fold_text(action.name + " " + action.keywords) for term in terms)
    )


def run_action(action: SystemAction) -> None:
    if action.uri:
        os.startfile(action.uri)
        return
    subprocess.Popen(list(action.command), creationflags=CREATE_NO_WINDOW)
