"""Rofi tarzı ek kipler: SSH sunucu başlatıcı ve Süreç (kill) yöneticisi."""

import ctypes
import os
import re
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from .query import fold_text, fuzzy_score


@dataclass(frozen=True)
class SshHost:
    alias: str
    hostname: str = ""
    user: str = ""
    port: str = ""

    @property
    def target_Spec(self) -> str:
        return self.alias

    @property
    def detail(self) -> str:
        parts = []
        if self.user and self.hostname:
            parts.append(f"{self.user}@{self.hostname}")
        elif self.hostname:
            parts.append(self.hostname)
        if self.port and self.port != "22":
            parts.append(f"port {self.port}")
        return "SSH · " + (" · ".join(parts) if parts else "Enter ile bağlan")


@dataclass(frozen=True)
class ProcessEntry:
    pid: int
    name: str
    memory_mb: float

    @property
    def display_title(self) -> str:
        return f"{self.name}   ({self.memory_mb:.1f} MB · PID {self.pid})"


def parse_ssh_config(ssh_dir: Path | None = None) -> tuple[SshHost, ...]:
    """~/.ssh/config ve known_hosts dosyalarından SSH hedeflerini çıkarır."""
    base = ssh_dir or (Path.home() / ".ssh")
    config_path = base / "config"
    hosts: dict[str, dict[str, str]] = {}
    current_aliases: list[str] = []

    if config_path.is_file():
        try:
            lines = config_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        for raw_line in lines:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            key, value = parts[0].casefold(), parts[1].strip()
            if key == "host":
                current_aliases = [
                    alias for alias in value.split()
                    if alias and "*" not in alias and "?" not in alias and not alias.startswith("!")
                ]
                for alias in current_aliases:
                    hosts.setdefault(alias, {"hostname": "", "user": "", "port": ""})
            elif key in ("hostname", "user", "port") and current_aliases:
                for alias in current_aliases:
                    if not hosts[alias].get(key):
                        hosts[alias][key] = value

    known_path = base / "known_hosts"
    if known_path.is_file():
        try:
            lines = known_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("|") or line.startswith("@"):
                continue
            host_field = line.split(None, 1)[0]
            for token in host_field.split(","):
                cleaned = re.sub(r"^\[([^\]]+)\]:\d+$", r"\1", token.strip())
                if cleaned and "*" not in cleaned and "?" not in cleaned and cleaned not in hosts:
                    hosts[cleaned] = {"hostname": cleaned, "user": "", "port": ""}

    result = [
        SshHost(alias=alias, hostname=info["hostname"], user=info["user"], port=info["port"])
        for alias, info in hosts.items()
    ]
    result.sort(key=lambda h: fold_text(h.alias))
    return tuple(result)


def search_ssh_hosts(query: str = "", ssh_dir: Path | None = None) -> tuple[SshHost, ...]:
    hosts = parse_ssh_config(ssh_dir)
    q = (query or "").strip()
    if not q:
        return hosts
    scored = []
    for host in hosts:
        haystack = f"{host.alias} {host.hostname} {host.user}"
        score = fuzzy_score(q, haystack)
        if score is not None:
            scored.append((score, host))
    scored.sort(key=lambda pair: (-pair[0], fold_text(pair[1].alias)))
    return tuple(host for _, host in scored)


# ---- Süreç (Kill) Yöneticisi -----------------------------------------------

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_TERMINATE = 0x0001
_SYSTEM_PIDS = frozenset((0, 4))


def list_processes() -> tuple[ProcessEntry, ...]:
    """Çalışan süreçleri bellek kullanımına göre azalan sırada döndürür."""
    if os.name != "nt":
        return ()

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)

    kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return ()

    own_pid = os.getpid()
    entries: list[ProcessEntry] = []
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            pid = int(pe.th32ProcessID)
            name = pe.szExeFile
            if pid not in _SYSTEM_PIDS and pid != own_pid and name:
                mem_mb = 0.0
                proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
                if not proc:
                    proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if proc:
                    try:
                        pmc = PROCESS_MEMORY_COUNTERS()
                        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                        if psapi.GetProcessMemoryInfo(proc, ctypes.byref(pmc), pmc.cb):
                            mem_mb = pmc.WorkingSetSize / (1024 * 1024)
                    finally:
                        kernel32.CloseHandle(proc)
                entries.append(ProcessEntry(pid=pid, name=name, memory_mb=mem_mb))
            ok = kernel32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        kernel32.CloseHandle(snap)

    entries.sort(key=lambda e: (-e.memory_mb, fold_text(e.name), e.pid))
    return tuple(entries)


def search_processes(query: str = "", limit: int = 80) -> tuple[ProcessEntry, ...]:
    processes = list_processes()
    q = (query or "").strip()
    if not q:
        return processes[:limit]
    scored = []
    for proc in processes:
        haystack = f"{proc.name} {proc.pid}"
        score = fuzzy_score(q, haystack)
        if score is not None:
            scored.append((score, proc))
    scored.sort(key=lambda pair: (-pair[0], -pair[1].memory_mb, pair[1].pid))
    return tuple(proc for _, proc in scored[:limit])


def kill_process(pid: int) -> None:
    """Belirtilen PID'li süreci sonlandırır."""
    if os.name != "nt":
        os.kill(int(pid), 9)
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
    if not handle:
        raise OSError(f"Süreç açılamadı (PID {pid}, hata {ctypes.get_last_error()}).")
    try:
        if not kernel32.TerminateProcess(handle, 1):
            raise OSError(f"Süreç sonlandırılamadı (PID {pid}, hata {ctypes.get_last_error()}).")
    finally:
        kernel32.CloseHandle(handle)
