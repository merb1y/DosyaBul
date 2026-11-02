"""Windows dosya/uygulama ikonlarini Tk PhotoImage olarak yukler."""

import ctypes
import os
import threading
from ctypes import wintypes

SHGFI_ICON = 0x00000100
SHGFI_LARGEICON = 0x00000000
SHGFI_SHELLICONSIZE = 0x00000004
SHGFI_USEFILEATTRIBUTES = 0x00000010
DIB_RGB_COLORS = 0


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wintypes.LONG),
        ("bmWidth", wintypes.LONG),
        ("bmHeight", wintypes.LONG),
        ("bmWidthBytes", wintypes.LONG),
        ("bmPlanes", wintypes.WORD),
        ("bmBitsPixel", wintypes.WORD),
        ("bmBits", ctypes.c_void_p),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class SHFILEINFO(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HICON),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", wintypes.WCHAR * 260),
        ("szTypeName", wintypes.WCHAR * 80),
    ]


if os.name == "nt":
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    _shell32.SHGetFileInfoW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFO), wintypes.UINT, wintypes.UINT,
    )
    _shell32.SHGetFileInfoW.restype = ctypes.c_void_p
    _user32.DestroyIcon.argtypes = (wintypes.HICON,)
    _user32.GetIconInfo.argtypes = (wintypes.HICON, ctypes.POINTER(ICONINFO))
    _gdi32.GetObjectW.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p)
    _gdi32.GetDIBits.argtypes = (
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    )
    _gdi32.DeleteObject.argtypes = (wintypes.HANDLE,)
    _user32.GetDC.argtypes = (wintypes.HWND,)
    _user32.GetDC.restype = wintypes.HDC
    _user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
else:
    _shell32 = _user32 = _gdi32 = None


def _hicon_to_image(hicon):
    """HICON'u (genislik, yukseklik, RGBA bytes) olarak dondurur."""
    info = ICONINFO()
    if not _user32.GetIconInfo(hicon, ctypes.byref(info)):
        return None
    try:
        if not info.hbmColor:
            return None
        bitmap = BITMAP()
        if not _gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(bitmap), ctypes.byref(bitmap)):
            return None
        width = int(bitmap.bmWidth)
        height = int(bitmap.bmHeight)
        if width <= 0 or height <= 0:
            return None
        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        dib = BITMAPINFO()
        dib.bmiHeader = header
        screen = _user32.GetDC(0)
        try:
            ok = _gdi32.GetDIBits(screen, info.hbmColor, 0, height, buffer, ctypes.byref(dib), DIB_RGB_COLORS)
        finally:
            if screen:
                _user32.ReleaseDC(0, screen)
        if not ok:
            return None
        raw = buffer.raw
        pixels = bytearray(width * height * 4)
        any_alpha = False
        for i in range(0, len(raw), 4):
            b, g, r, a = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
            if a:
                any_alpha = True
            pixels[i] = r
            pixels[i + 1] = g
            pixels[i + 2] = b
            pixels[i + 3] = a
        if not any_alpha:
            for i in range(3, len(pixels), 4):
                pixels[i] = 255
        return width, height, bytes(pixels)
    finally:
        if info.hbmColor:
            _gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask:
            _gdi32.DeleteObject(info.hbmMask)


def _icon_handle_for(path, use_attributes=False):
    info = SHFILEINFO()
    flags = SHGFI_ICON | SHGFI_SHELLICONSIZE
    if use_attributes:
        flags |= SHGFI_USEFILEATTRIBUTES
    result = _shell32.SHGetFileInfoW(str(path), 0, ctypes.byref(info), ctypes.sizeof(info), flags)
    if not result or not info.hIcon:
        return None
    return info.hIcon


def load_icon(path):
    """Bir dosya/klasor/kisayolu yolundan ikonu (w, h, rgba_bytes) olarak yukler."""
    if os.name != "nt" or _shell32 is None or not path:
        return None
    icon = None
    try:
        icon = _icon_handle_for(path)
        if icon is None:
            icon = _icon_handle_for(path, use_attributes=True)
        if icon is None:
            return None
        return _hicon_to_image(icon)
    except OSError:
        return None
    finally:
        if icon:
            _user32.DestroyIcon(icon)

