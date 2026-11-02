from pathlib import Path


def discover_drives() -> tuple[Path, ...]:
    """Sabit ve çıkarılabilir sürücüleri listeler."""
    drives = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        candidate = Path(f"{letter}:\\")
        if candidate.exists():
            drives.append(candidate)
    return tuple(drives)
