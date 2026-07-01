from __future__ import annotations

import asyncio
import subprocess
import ctypes
from pathlib import Path
from aiohttp import web

try:
    from server import PromptServer
except Exception:
    PromptServer = None


import sys
import shutil


def _route_post(path: str):
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return lambda handler: handler
    return server.routes.post(path)


def _configure_windows_dialog_api():
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    user32.GetParent.argtypes = [ctypes.c_void_p]
    user32.GetParent.restype = ctypes.c_void_p
    user32.SendMessageW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    user32.SendMessageW.restype = ctypes.c_void_p
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]


def _windows_foreground_window():
    _configure_windows_dialog_api()
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    return hwnd or None


def _show_windows_dialog_window(hwnd):
    _configure_windows_dialog_api()
    if not hwnd:
        return
    hwnd_topmost = ctypes.c_void_p(-1)
    hwnd_notopmost = ctypes.c_void_p(-2)
    swp_nomove = 0x0002
    swp_nosize = 0x0001
    swp_showwindow = 0x0040
    ctypes.windll.user32.ShowWindow(hwnd, 5)
    ctypes.windll.user32.SetWindowPos(
        hwnd,
        hwnd_topmost,
        0,
        0,
        0,
        0,
        swp_nomove | swp_nosize | swp_showwindow,
    )
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    ctypes.windll.user32.SetWindowPos(
        hwnd,
        hwnd_notopmost,
        0,
        0,
        0,
        0,
        swp_nomove | swp_nosize | swp_showwindow,
    )


class _WindowsGUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _WindowsFilterSpec(ctypes.Structure):
    _fields_ = [
        ("pszName", ctypes.c_wchar_p),
        ("pszSpec", ctypes.c_wchar_p),
    ]


def _windows_guid(text: str) -> _WindowsGUID:
    guid = _WindowsGUID()
    result = ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(guid))
    if result < 0:
        raise RuntimeError(f"Invalid Windows GUID: {text}")
    return guid


def _windows_com_method(interface, index, restype, *argtypes):
    vtable = ctypes.cast(interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return prototype(vtable[index])


def _windows_hresult_cancelled(result: int) -> bool:
    return result & 0xFFFFFFFF == 0x800704C7


def _windows_check_hresult(result: int, action: str):
    if result < 0:
        raise RuntimeError(f"{action} failed with HRESULT 0x{result & 0xFFFFFFFF:08X}.")


def _windows_release_com(interface):
    if interface:
        _windows_com_method(interface, 2, ctypes.c_ulong)(interface)


def _windows_shell_item_from_path(path: Path):
    item = ctypes.c_void_p()
    iid_shell_item = _windows_guid("{43826D1E-E718-42EE-BC55-A1E261C37BFE}")
    result = ctypes.windll.shell32.SHCreateItemFromParsingName(
        ctypes.c_wchar_p(str(path)),
        None,
        ctypes.byref(iid_shell_item),
        ctypes.byref(item),
    )
    if result < 0:
        return None
    return item


def _choose_windows_with_explorer_dialog(
    title: str,
    initial_path: Path,
    *,
    pick_folder: bool,
) -> str:
    clsid_file_open_dialog = _windows_guid("{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}")
    iid_file_open_dialog = _windows_guid("{D57C7288-D4AD-4768-BE02-9D969532D960}")
    dialog = ctypes.c_void_p()
    initialized_com = False

    result = ctypes.windll.ole32.CoInitializeEx(None, 2)
    if result in (0, 1):
        initialized_com = True
    elif result & 0xFFFFFFFF != 0x80010106:
        _windows_check_hresult(result, "Windows COM initialization")

    try:
        result = ctypes.windll.ole32.CoCreateInstance(
            ctypes.byref(clsid_file_open_dialog),
            None,
            1,
            ctypes.byref(iid_file_open_dialog),
            ctypes.byref(dialog),
        )
        _windows_check_hresult(result, "Windows Explorer file dialog creation")

        fos_nochangedir = 0x00000008
        fos_pickfolders = 0x00000020
        fos_forcefilesystem = 0x00000040
        fos_pathmustexist = 0x00000800
        fos_filemustexist = 0x00001000

        options = fos_nochangedir | fos_forcefilesystem | fos_pathmustexist
        if pick_folder:
            options |= fos_pickfolders
        else:
            options |= fos_filemustexist

        set_options = _windows_com_method(dialog, 9, ctypes.c_long, ctypes.c_uint)
        _windows_check_hresult(set_options(dialog, options), "Windows Explorer dialog options")

        set_title = _windows_com_method(dialog, 17, ctypes.c_long, ctypes.c_wchar_p)
        _windows_check_hresult(set_title(dialog, title), "Windows Explorer dialog title")

        initial_directory = initial_path if initial_path.is_dir() else initial_path.parent
        if not initial_directory.is_dir():
            initial_directory = Path.home()
        folder_item = _windows_shell_item_from_path(initial_directory)
        if folder_item:
            try:
                set_folder = _windows_com_method(dialog, 12, ctypes.c_long, ctypes.c_void_p)
                _windows_check_hresult(
                    set_folder(dialog, folder_item),
                    "Windows Explorer dialog initial folder",
                )
            finally:
                _windows_release_com(folder_item)

        if not pick_folder:
            filters = (_WindowsFilterSpec * 2)(
                _WindowsFilterSpec(
                    "图片文件",
                    "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tif;*.tiff",
                ),
                _WindowsFilterSpec("所有文件", "*.*"),
            )
            set_file_types = _windows_com_method(
                dialog,
                4,
                ctypes.c_long,
                ctypes.c_uint,
                ctypes.POINTER(_WindowsFilterSpec),
            )
            _windows_check_hresult(
                set_file_types(dialog, len(filters), filters),
                "Windows Explorer dialog file filters",
            )
            if initial_path.is_file():
                set_file_name = _windows_com_method(dialog, 15, ctypes.c_long, ctypes.c_wchar_p)
                _windows_check_hresult(
                    set_file_name(dialog, initial_path.name),
                    "Windows Explorer dialog file name",
                )

        show = _windows_com_method(dialog, 3, ctypes.c_long, ctypes.c_void_p)
        result = show(dialog, _windows_foreground_window())
        if _windows_hresult_cancelled(result):
            return ""
        _windows_check_hresult(result, "Windows Explorer dialog")

        selected_item = ctypes.c_void_p()
        get_result = _windows_com_method(
            dialog,
            20,
            ctypes.c_long,
            ctypes.POINTER(ctypes.c_void_p),
        )
        _windows_check_hresult(
            get_result(dialog, ctypes.byref(selected_item)),
            "Windows Explorer dialog result",
        )
        try:
            selected_path = ctypes.c_void_p()
            get_display_name = _windows_com_method(
                selected_item,
                5,
                ctypes.c_long,
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_void_p),
            )
            _windows_check_hresult(
                get_display_name(selected_item, 0x80058000, ctypes.byref(selected_path)),
                "Windows Explorer dialog selected path",
            )
            try:
                value = ctypes.cast(selected_path, ctypes.c_wchar_p).value
                return (value or "").strip()
            finally:
                ctypes.windll.ole32.CoTaskMemFree(selected_path)
        finally:
            _windows_release_com(selected_item)
    finally:
        _windows_release_com(dialog)
        if initialized_com:
            ctypes.windll.ole32.CoUninitialize()


def _choose_windows_directory(initial_directory: str) -> str:
    initial = Path(initial_directory).expanduser()
    if not initial.is_dir():
        initial = Path.home()
    return _choose_windows_with_explorer_dialog(
        "选择输入目录",
        initial,
        pick_folder=True,
    )


def _choose_windows_image_file(initial_path: str) -> str:
    initial = Path(initial_path).expanduser()
    initial_directory = initial.parent if initial.is_file() else initial
    if not initial_directory.is_dir():
        initial_directory = Path.home()
    return _choose_windows_with_explorer_dialog(
        "选择输入图片",
        initial if initial.is_file() else initial_directory,
        pick_folder=False,
    )


def _choose_linux_directory(initial_directory: str) -> str:
    initial = Path(initial_directory).expanduser()
    if not initial.is_dir():
        initial = Path.home()
    if shutil.which("zenity"):
        cmd = [
            "zenity",
            "--file-selection",
            "--directory",
            "--title=选择目录",
            f"--filename={initial}/",
        ]
        return _run_linux_dialog(cmd, "Zenity directory selector")
    if shutil.which("kdialog"):
        cmd = ["kdialog", "--getexistingdirectory", str(initial), "选择目录"]
        return _run_linux_dialog(cmd, "KDialog directory selector")
    raise RuntimeError(
        "No Linux file dialog tool found. Please install zenity or kdialog."
    )


def _choose_linux_image_file(initial_path: str) -> str:
    initial = Path(initial_path).expanduser()
    initial_directory = initial.parent if initial.is_file() else initial
    if not initial_directory.is_dir():
        initial_directory = Path.home()
    if shutil.which("zenity"):
        cmd = [
            "zenity",
            "--file-selection",
            "--title=选择图片文件",
            f"--filename={initial_directory}/",
            "--file-filter=图片文件 | *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.PNG *.JPG *.JPEG *.WEBP *.BMP *.TIF *.TIFF",
            "--file-filter=所有文件 | *",
        ]
        return _run_linux_dialog(cmd, "Zenity file selector")
    if shutil.which("kdialog"):
        cmd = [
            "kdialog",
            "--getopenfilename",
            str(initial_directory),
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        ]
        return _run_linux_dialog(cmd, "KDialog file selector")
    raise RuntimeError(
        "No Linux file dialog tool found. Please install zenity or kdialog."
    )


def _run_linux_dialog(cmd: list[str], label: str) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        if result.returncode == 1:
            return ""
        raise RuntimeError(result.stderr.strip() or f"{label} exited with code {result.returncode}")
    except Exception as error:
        raise RuntimeError(f"{label} failed: {error}") from error


def _choose_directory(initial_directory: str) -> str:
    if sys.platform.startswith("win"):
        return _choose_windows_directory(initial_directory)
    if sys.platform.startswith("linux"):
        return _choose_linux_directory(initial_directory)
    raise RuntimeError("Only Windows and Linux/Fedora file pickers are supported.")


def _choose_image_file(initial_path: str) -> str:
    if sys.platform.startswith("win"):
        return _choose_windows_image_file(initial_path)
    if sys.platform.startswith("linux"):
        return _choose_linux_image_file(initial_path)
    raise RuntimeError("Only Windows and Linux/Fedora file pickers are supported.")


@_route_post("/ks-product-split/select-directory")
async def ks_select_product_directory(request):
    payload = await request.json()
    initial = str(payload.get("initial_directory", ""))
    try:
        selected = await asyncio.to_thread(_choose_directory, initial)
        return web.json_response({"path": selected, "cancelled": not bool(selected)})
    except Exception as error:
        return web.json_response({"error": str(error)}, status=500)


@_route_post("/ks-product-split/select-image-file")
async def ks_select_product_image_file(request):
    payload = await request.json()
    initial = str(payload.get("initial_path", ""))
    try:
        selected = await asyncio.to_thread(_choose_image_file, initial)
        return web.json_response({"path": selected, "cancelled": not bool(selected)})
    except Exception as error:
        return web.json_response({"error": str(error)}, status=500)


