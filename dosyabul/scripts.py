"""Rofi 'script modi': scripts klasöründeki betikler liste üretir, seçilen satır betiğe argüman olur."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .query import fold_text

SCRIPT_SUFFIXES = (".py", ".ps1", ".cmd", ".bat")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
MAX_LINES = 200
TIMEOUT = 10

EXAMPLE_NAME = "ornek.py"
EXAMPLE = '''# DosyaBul betik örneği.
# Argümansız çalışınca her satır bir seçenek olur.
# Bir satır seçilince betik o satırla (argüman olarak) yeniden çalışır;
# çıktı boşsa panel kapanır, doluysa yeni liste gösterilir.
import sys

if len(sys.argv) < 2:
    print("Merhaba")
    print("Dünya")
else:
    print("Seçtin: " + sys.argv[1], file=sys.stderr)
'''


def scripts_dir(data_dir) -> Path:
    return Path(data_dir) / "scripts"


def ensure_example(data_dir) -> Path:
    folder = scripts_dir(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    example = folder / EXAMPLE_NAME
    if not any(path.suffix.lower() in SCRIPT_SUFFIXES for path in folder.iterdir()):
        example.write_text(EXAMPLE, encoding="utf-8")
    return folder


def list_scripts(data_dir, query: str = "") -> tuple[Path, ...]:
    folder = scripts_dir(data_dir)
    try:
        files = [path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in SCRIPT_SUFFIXES]
    except OSError:
        return ()
    terms = tuple(part for part in fold_text(query).split() if part)
    files = [path for path in files if all(term in fold_text(path.stem) for term in terms)]
    return tuple(sorted(files, key=lambda path: path.name.casefold()))


def build_command(script: Path, argument: str | None = None) -> list[str]:
    suffix = script.suffix.lower()
    if suffix == ".py":
        interpreter = shutil.which("python") or shutil.which("py")
        if not interpreter and not getattr(sys, "frozen", False):
            interpreter = sys.executable
        if not interpreter:
            raise FileNotFoundError("Python bulunamadı; .py betikleri için Python kur.")
        command = [interpreter, str(script)]
    elif suffix == ".ps1":
        powershell = shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"
        command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    elif suffix in (".cmd", ".bat"):
        command = ["cmd.exe", "/c", str(script)]
    else:
        raise ValueError("Desteklenmeyen betik türü.")
    if argument is not None:
        command.append(argument)
    return command


def run_script(script: Path, argument: str | None = None, timeout: int = TIMEOUT) -> tuple[str, ...]:
    """Betiği çalıştırır, stdout satırlarını döndürür. Hatalarda OSError/ValueError yükseltir."""
    command = build_command(script, argument)
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW,
            cwd=str(script.parent), env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except subprocess.TimeoutExpired as error:
        raise OSError(f"Betik {timeout} saniyede bitmedi.") from error
    text = completed.stdout.decode("utf-8", errors="replace")
    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
    return lines[:MAX_LINES]
