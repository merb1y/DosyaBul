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
MAX_PATH = 260

CLSCTX_INPROC_SERVER = 0x1
COINIT_APARTMENTTHREADED = 0x2
RPC_E_CHANGED_MODE = 0x80010106
S_OK = 0
S_FALSE = 1
SLGP_RAWPATH = 0x00000004

SIIGBF_BIGGERSIZEOK = 0x00000001
SIIGBF_ICONONLY = 0x00000004

ICON_SIZE = 32


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, text):
        super().__init__()
        parts = text.strip("{}").split("-")
        self.Data1 = int(parts[0], 16)
        self.Data2 = int(parts[1], 16)
        self.Data3 = int(parts[2], 16)
        tail = parts[3] + parts[4]
        for index in range(8):
            self.Data4[index] = int(tail[index * 2:index * 2 + 2], 16)


CLSID_SHELL_LINK = GUID("{00021401-0000-0000-C000-000000000046}")
IID_ISHELL_LINK_W = GUID("{000214F9-0000-0000-C000-000000000046}")
IID_IPERSIST_FILE = GUID("{0000010B-0000-0000-C000-000000000046}")
IID_ISHELL_ITEM = GUID("{43826d1e-e718-42ee-bc55-a1e261c37bfe}")
IID_ISHELL_ITEM_IMAGE_FACTORY = GUID("{bcc18b79-ba16-442f-80c4-8a59c30c463b}")


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
    _ole32 = ctypes.WinDLL("ole32", use_last_error=True)

    _shell32.SHGetFileInfoW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFO), wintypes.UINT, wintypes.UINT,
    )
    _shell32.SHGetFileInfoW.restype = ctypes.c_void_p
    _shell32.ExtractIconExW.argtypes = (
        wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON), wintypes.UINT,
    )
    _shell32.ExtractIconExW.restype = wintypes.UINT
    _shell32.SHCreateItemFromParsingName.argtypes = (
        wintypes.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
    )
    _shell32.SHCreateItemFromParsingName.restype = ctypes.c_long
    _user32.DestroyIcon.argtypes = (wintypes.HICON,)
    _user32.GetIconInfo.argtypes = (wintypes.HICON, ctypes.POINTER(ICONINFO))
    _user32.GetDC.argtypes = (wintypes.HWND,)
    _user32.GetDC.restype = wintypes.HDC
    _user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
    _gdi32.GetObjectW.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p)
    _gdi32.GetDIBits.argtypes = (
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    )
    _gdi32.DeleteObject.argtypes = (wintypes.HANDLE,)
    _ole32.CoInitializeEx.argtypes = (ctypes.c_void_p, wintypes.DWORD)
    _ole32.CoInitializeEx.restype = ctypes.c_long
    _ole32.CoCreateInstance.argtypes = (
        ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
    )
    _ole32.CoCreateInstance.restype = ctypes.c_long
else:
    _shell32 = _user32 = _gdi32 = _ole32 = None

_com_ready = threading.local()


def _bitmap_to_image(hbitmap):
    """HBITMAP'i (genislik, yukseklik, RGBA bytes) olarak dondurur."""
    bitmap = BITMAP()
    if not _gdi32.GetObjectW(hbitmap, ctypes.sizeof(bitmap), ctypes.byref(bitmap)):
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
        ok = _gdi32.GetDIBits(screen, hbitmap, 0, height, buffer, ctypes.byref(dib), DIB_RGB_COLORS)
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


def _hicon_to_image(hicon):
    """HICON'u (genislik, yukseklik, RGBA bytes) olarak dondurur."""
    info = ICONINFO()
    if not _user32.GetIconInfo(hicon, ctypes.byref(info)):
        return None
    try:
        if not info.hbmColor:
            return None
        return _bitmap_to_image(info.hbmColor)
    finally:
        if info.hbmColor:
            _gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask:
            _gdi32.DeleteObject(info.hbmMask)


def _com_interface(pointer, index, *argtypes):
    """Bir COM arayuzunun vtable metodunu, nesneye bagli olarak dondurur."""
    vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
    method = prototype(vtable[index])

    def call(*args):
        return method(pointer, *args)

    return call


def _ensure_com():
    if getattr(_com_ready, "ok", False):
        return True
    result = _ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    # S_FALSE: bu is parcacigi icin zaten baslatilmis.
    # RPC_E_CHANGED_MODE: baska bir daire modeliyle baslatilmis; yine de kullanilabilir.
    _com_ready.ok = result in (S_OK, S_FALSE, RPC_E_CHANGED_MODE)
    return _com_ready.ok


def _image_from_shell_item(path, size=ICON_SIZE):
    """Kabuk ogesi goruntu fabrikasiyla temiz (overlaysiz) ikon uretir.

    Kabuk, .lnk/.url kisayollarina ikon cizerken sol alt koseye "kisayol oku"
    yerlesimi ekler. IShellItemImageFactory bu yerlesimi eklemeden uygulamanin
    kendi logosunu dondurur.
    """
    if not _ensure_com():
        return None
    item = ctypes.c_void_p()
    if _shell32.SHCreateItemFromParsingName(
        str(path), None, ctypes.byref(IID_ISHELL_ITEM), ctypes.byref(item),
    ) != S_OK or not item:
        return None
    factory = ctypes.c_void_p()
    try:
        query_interface = _com_interface(item, 0, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
        if query_interface(
            ctypes.byref(IID_ISHELL_ITEM_IMAGE_FACTORY), ctypes.byref(factory),
        ) != S_OK or not factory:
            return None
        try:
            get_image = _com_interface(factory, 3, wintypes.SIZE, ctypes.c_int, ctypes.POINTER(wintypes.HBITMAP))
            bitmap = wintypes.HBITMAP()
            flags = SIIGBF_ICONONLY | SIIGBF_BIGGERSIZEOK
            if get_image(wintypes.SIZE(int(size), int(size)), flags, ctypes.byref(bitmap)) != S_OK or not bitmap:
                return None
            try:
                return _bitmap_to_image(bitmap)
            finally:
                _gdi32.DeleteObject(bitmap)
        finally:
            release = _com_interface(factory, 2)
            release()
    finally:
        release = _com_interface(item, 2)
        release()


def _icon_handle_for(path, use_attributes=False):
    info = SHFILEINFO()
    flags = SHGFI_ICON | SHGFI_SHELLICONSIZE
    if use_attributes:
        flags |= SHGFI_USEFILEATTRIBUTES
    result = _shell32.SHGetFileInfoW(str(path), 0, ctypes.byref(info), ctypes.sizeof(info), flags)
    if not result or not info.hIcon:
        return None
    return info.hIcon


def _image_from_path(path):
    """SHGetFileInfo ile bir yolun ikonunu yukler."""
    icon = None
    try:
        for use_attributes in (False, True):
            icon = _icon_handle_for(path, use_attributes=use_attributes)
            if icon:
                data = _hicon_to_image(icon)
                if data is not None:
                    return data
                _user32.DestroyIcon(icon)
                icon = None
    except OSError:
        return None
    finally:
        if icon:
            _user32.DestroyIcon(icon)
    return None


def _image_from_index(path, index):
    """ExtractIconEx ile ikon kaynagindan belirli siradaki ikonu yukler.

    Negatif degerler kaynak dosyasindaki ikon kimligini (resource ID) secer;
    kabuk kisayollarinda bu bicim yaygin oldugu icin desteklenir.
    """
    if index is None or not os.path.isfile(path):
        return None
    large = wintypes.HICON()
    try:
        # ExtractIconEx icin -1 "tum ikonlar" demektir; tek ikon isterken kullanilmaz.
        if int(index) == -1:
            return None
        count = _shell32.ExtractIconExW(str(path), int(index), ctypes.byref(large), None, 1)
    except OSError:
        return None
    if not count or not large:
        return None
    try:
        return _hicon_to_image(large)
    finally:
        _user32.DestroyIcon(large)


def _expand_environment(path):
    if not path:
        return None
    expanded = os.path.expandvars(path)
    return expanded if expanded and "%" not in expanded else None


def _shortcut_details(path):
    """Bir .lnk dosyasinin hedef yolunu ve ikon kaynagini dondurur."""
    if not path.casefold().endswith(".lnk") or not _ensure_com():
        return None, None, None
    link = ctypes.c_void_p()
    if _ole32.CoCreateInstance(
        ctypes.byref(CLSID_SHELL_LINK), None, CLSCTX_INPROC_SERVER,
        ctypes.byref(IID_ISHELL_LINK_W), ctypes.byref(link),
    ) != S_OK or not link:
        return None, None, None
    persist = ctypes.c_void_p()
    try:
        query_interface = _com_interface(link, 0, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
        if query_interface(ctypes.byref(IID_IPERSIST_FILE), ctypes.byref(persist)) != S_OK or not persist:
            return None, None, None
        try:
            load = _com_interface(persist, 5, wintypes.LPCWSTR, wintypes.DWORD)
            if load(str(path), 0) != S_OK:
                return None, None, None
            target_buffer = ctypes.create_unicode_buffer(MAX_PATH)
            get_path = _com_interface(
                link, 3, wintypes.LPWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
            )
            # SLGP_RAWPATH: ortam degiskeni iceren hedefleri de okur.
            for flags in (0, SLGP_RAWPATH):
                target_buffer.value = ""
                get_path(target_buffer, MAX_PATH, None, flags)
                if target_buffer.value:
                    break
            icon_buffer = ctypes.create_unicode_buffer(MAX_PATH)
            icon_index = ctypes.c_int()
            get_icon = _com_interface(link, 16, wintypes.LPWSTR, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
            get_icon(icon_buffer, MAX_PATH, ctypes.byref(icon_index))
            target = _expand_environment(target_buffer.value)
            icon_location = _expand_environment(icon_buffer.value)
            index = icon_index.value if icon_location else None
            if icon_location and not os.path.isfile(icon_location):
                icon_location = None
                index = None
            return target, icon_location, index
        finally:
            release = _com_interface(persist, 2)
            release()
    finally:
        release = _com_interface(link, 2)
        release()


def _internet_shortcut_details(path):
    """Bir .url dosyasindaki IconFile ve URL satirlarini okur."""
    if not path.casefold().endswith(".url"):
        return None, None, None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return None, None, None
    values = {}
    for line in lines:
        name, separator, value = line.partition("=")
        if separator:
            values[name.strip().casefold()] = value.strip().strip('"')
    icon_location = _expand_environment(values.get("iconfile"))
    if icon_location and not os.path.isfile(icon_location):
        icon_location = None
    index = values.get("iconindex")
    try:
        index = int(index) if index is not None else None
    except ValueError:
        index = None
    return values.get("url") or None, icon_location, index


ICON_SOURCE_SUFFIXES = (".exe", ".dll", ".ico", ".cpl", ".scr", ".icl", ".mun", ".ocx")


def _icon_candidates(path):
    """Kisayolun bildirdigi ikon kaynagini ve hedefini sirayla uretir."""
    path = str(path)
    target, icon_location, index = (None, None, None)
    try:
        if path.casefold().endswith(".lnk"):
            target, icon_location, index = _shortcut_details(path)
        elif path.casefold().endswith(".url"):
            target, icon_location, index = _internet_shortcut_details(path)
    except (OSError, ValueError):
        target, icon_location, index = (None, None, None)
    if icon_location:
        yield icon_location, index
    if target and target.casefold().endswith(ICON_SOURCE_SUFFIXES) and os.path.isfile(target):
        yield target, None


def _image_from_shortcut(path):
    """Kisayolun bildirdigi ikonu, oku yerlesimi olmadan uretir."""
    for candidate, index in _icon_candidates(path):
        # Aday yol bir kisayolsa kabuk ikona "kisayol oku" bindirir; bu yuzden
        # yalnizca gercek ikon kaynaklarindan (exe/dll/ico/...) okuma yapilir.
        if _is_shortcut(candidate):
            continue
        data = _image_from_index(candidate, index)
        if data is None:
            data = _image_from_path(candidate)
        if data is not None:
            return data
    return None


def _is_shortcut(path):
    return path.casefold().endswith((".lnk", ".url", ".appref-ms"))


def load_icon(path):
    """Bir dosya/klasor/kisayolu yolundan ikonu (w, h, rgba_bytes) olarak yukler."""
    if os.name != "nt" or _shell32 is None or not path:
        return None
    path = str(path)
    try:
        if _is_shortcut(path):
            # Kisayollarda kabuk, ikonun sol alt kosesine "kisayol oku" yerlesimi
            # ekler. Once kisayolun bildirdigi ikon, sonra okusuz kabuk goruntusu
            # denenir. Son care olarak okla birlikte gostermek yerine hedefin
            # kendi ikonu zorlanir; boylece ok hicbir durumda cizilmez.
            data = _image_from_shortcut(path)
            if data is not None:
                return data
            data = _image_from_shell_item(path)
            if data is not None:
                return data
            return None
        data = _image_from_path(path)
        if data is not None:
            return data
        return _image_from_shell_item(path)
    except OSError:
        return None
