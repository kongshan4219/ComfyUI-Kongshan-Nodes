from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path
from aiohttp import web

from server import PromptServer


import sys
import shutil


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


def _route_post(path: str):
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return lambda handler: handler
    return server.routes.post(path)


def _natural_sort_key(path: Path) -> list:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", path.name)]


def _list_image_names(directory_path: str, pattern: str) -> list[str]:
    directory = Path(directory_path).expanduser()
    if not directory.is_dir():
        return []

    extensions: list[str] = []
    if pattern.strip():
        parts = re.split(r"[,;]+", pattern)
        for part in parts:
            cleaned = part.strip().lower().lstrip("*").lstrip(".")
            if cleaned:
                extensions.append("." + cleaned)
    if not extensions:
        extensions = list(IMAGE_EXTENSIONS)

    return [
        path.name
        for path in sorted(
            (
                path
                for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() in extensions
            ),
            key=_natural_sort_key,
        )
    ]


def _choose_windows_directory(initial_directory: str) -> str:
    initial = Path(initial_directory).expanduser()
    if not initial.is_dir():
        initial = Path.home()
    escaped = str(initial).replace("'", "''")
    script = rf"""
$culture = [System.Globalization.CultureInfo]::InstalledUICulture
try {{
    $language = (Get-WinUserLanguageList | Select-Object -First 1).LanguageTag
    if ($language) {{
        $culture = [System.Globalization.CultureInfo]::GetCultureInfo($language)
    }}
}} catch {{}}
[System.Threading.Thread]::CurrentThread.CurrentCulture = $culture
[System.Threading.Thread]::CurrentThread.CurrentUICulture = $culture
[System.Globalization.CultureInfo]::DefaultThreadCurrentCulture = $culture
[System.Globalization.CultureInfo]::DefaultThreadCurrentUICulture = $culture
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$owner = New-Object System.Windows.Forms.Form
$owner.Text = '空山节点'
$owner.Size = New-Object System.Drawing.Size(1, 1)
$owner.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$owner.ShowInTaskbar = $false
$owner.TopMost = $true
$owner.Opacity = 0
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择输入目录'
$dialog.ShowNewFolderButton = $true
$dialog.SelectedPath = '{escaped}'
if ($dialog.PSObject.Properties.Name -contains 'UseDescriptionForTitle') {{
    $dialog.UseDescriptionForTitle = $true
}}
try {{
    $owner.Show()
    $owner.Activate()
    if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {{
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        Write-Output $dialog.SelectedPath
    }}
}} finally {{
    $dialog.Dispose()
    $owner.Close()
    $owner.Dispose()
}}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Directory selector failed")
    return result.stdout.strip()


def _choose_windows_image_file(initial_path: str) -> str:
    initial = Path(initial_path).expanduser()
    initial_directory = initial.parent if initial.is_file() else initial
    if not initial_directory.is_dir():
        initial_directory = Path.home()
    escaped = str(initial_directory).replace("'", "''")
    script = rf"""
$culture = [System.Globalization.CultureInfo]::InstalledUICulture
try {{
    $language = (Get-WinUserLanguageList | Select-Object -First 1).LanguageTag
    if ($language) {{
        $culture = [System.Globalization.CultureInfo]::GetCultureInfo($language)
    }}
}} catch {{}}
[System.Threading.Thread]::CurrentThread.CurrentCulture = $culture
[System.Threading.Thread]::CurrentThread.CurrentUICulture = $culture
[System.Globalization.CultureInfo]::DefaultThreadCurrentCulture = $culture
[System.Globalization.CultureInfo]::DefaultThreadCurrentUICulture = $culture
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$owner = New-Object System.Windows.Forms.Form
$owner.Text = '空山节点'
$owner.Size = New-Object System.Drawing.Size(1, 1)
$owner.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$owner.ShowInTaskbar = $false
$owner.TopMost = $true
$owner.Opacity = 0
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '选择输入图片'
$dialog.InitialDirectory = '{escaped}'
$dialog.Filter = '图片文件|*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tif;*.tiff|所有文件|*.*'
$dialog.Multiselect = $false
try {{
    $owner.Show()
    $owner.Activate()
    if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {{
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        Write-Output $dialog.FileName
    }}
}} finally {{
    $dialog.Dispose()
    $owner.Close()
    $owner.Dispose()
}}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Image selector failed")
    return result.stdout.strip()


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


@_route_post("/ks-product-split/list-images")
async def ks_list_product_images(request):
    payload = await request.json()
    directory_path = str(payload.get("directory_path", ""))
    pattern = str(payload.get("pattern", ""))
    try:
        images = await asyncio.to_thread(_list_image_names, directory_path, pattern)
        return web.json_response({"images": images})
    except Exception as error:
        return web.json_response({"error": str(error)}, status=500)

