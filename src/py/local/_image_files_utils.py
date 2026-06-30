from __future__ import annotations

import asyncio
import subprocess
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


def _choose_windows_directory(initial_directory: str) -> str:
    initial = Path(initial_directory).expanduser()
    if not initial.is_dir():
        initial = Path.home()
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as error:
        raise RuntimeError(f"Python directory selector requires tkinter: {error}") from error

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected = filedialog.askdirectory(
            parent=root,
            title="选择输入目录",
            initialdir=str(initial),
            mustexist=True,
        )
        return str(selected or "").strip()
    finally:
        root.destroy()


def _choose_windows_image_file(initial_path: str) -> str:
    initial = Path(initial_path).expanduser()
    initial_directory = initial.parent if initial.is_file() else initial
    if not initial_directory.is_dir():
        initial_directory = Path.home()
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as error:
        raise RuntimeError(f"Python image selector requires tkinter: {error}") from error

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected = filedialog.askopenfilename(
            parent=root,
            title="选择输入图片",
            initialdir=str(initial_directory),
            initialfile=initial.name if initial.is_file() else "",
            filetypes=(
                ("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
                ("所有文件", "*.*"),
            ),
        )
        return str(selected or "").strip()
    finally:
        root.destroy()


def _choose_linux_directory(initial_directory: str) -> str:
    initial = Path(initial_directory).expanduser()
    if not initial.is_dir():
        initial = Path.home()
    if not shutil.which("zenity"):
        raise RuntimeError("Zenity is not installed. Please install it (e.g. sudo apt install zenity).")
    cmd = [
        "zenity",
        "--file-selection",
        "--directory",
        "--title=选择目录",
        f"--filename={initial}/",
    ]
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
        elif result.returncode == 1:
            return ""
        else:
            raise RuntimeError(result.stderr.strip() or f"Zenity exited with code {result.returncode}")
    except Exception as e:
        raise RuntimeError(f"Zenity directory selector failed: {e}")


def _choose_linux_image_file(initial_path: str) -> str:
    initial = Path(initial_path).expanduser()
    initial_directory = initial.parent if initial.is_file() else initial
    if not initial_directory.is_dir():
        initial_directory = Path.home()
    if not shutil.which("zenity"):
        raise RuntimeError("Zenity is not installed. Please install it (e.g. sudo apt install zenity).")
    cmd = [
        "zenity",
        "--file-selection",
        "--title=选择图片文件",
        f"--filename={initial_directory}/",
        "--file-filter=图片文件 | *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.PNG *.JPG *.JPEG *.WEBP *.BMP *.TIF *.TIFF",
        "--file-filter=所有文件 | *",
    ]
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
        elif result.returncode == 1:
            return ""
        else:
            raise RuntimeError(result.stderr.strip() or f"Zenity exited with code {result.returncode}")
    except Exception as e:
        raise RuntimeError(f"Zenity file selector failed: {e}")


def _choose_macos_directory(initial_directory: str) -> str:
    initial = Path(initial_directory).expanduser()
    if not initial.is_dir():
        initial = Path.home()
    script = f'POSIX path of (choose folder with prompt "选择目录" default location POSIX file "{initial}")'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        elif "User canceled" in result.stderr or result.returncode == 1:
            return ""
        else:
            raise RuntimeError(result.stderr.strip() or f"osascript exited with code {result.returncode}")
    except Exception as e:
        raise RuntimeError(f"macOS directory selector failed: {e}")


def _choose_macos_image_file(initial_path: str) -> str:
    initial = Path(initial_path).expanduser()
    initial_directory = initial.parent if initial.is_file() else initial
    if not initial_directory.is_dir():
        initial_directory = Path.home()
    script = f'POSIX path of (choose file with prompt "选择图片文件" of type {{"public.image"}} default location POSIX file "{initial_directory}")'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        elif "User canceled" in result.stderr or result.returncode == 1:
            return ""
        else:
            raise RuntimeError(result.stderr.strip() or f"osascript exited with code {result.returncode}")
    except Exception as e:
        raise RuntimeError(f"macOS file selector failed: {e}")


def _choose_directory(initial_directory: str) -> str:
    if sys.platform.startswith("win"):
        return _choose_windows_directory(initial_directory)
    elif sys.platform.startswith("darwin"):
        return _choose_macos_directory(initial_directory)
    else:
        return _choose_linux_directory(initial_directory)


def _choose_image_file(initial_path: str) -> str:
    if sys.platform.startswith("win"):
        return _choose_windows_image_file(initial_path)
    elif sys.platform.startswith("darwin"):
        return _choose_macos_image_file(initial_path)
    else:
        return _choose_linux_image_file(initial_path)


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


