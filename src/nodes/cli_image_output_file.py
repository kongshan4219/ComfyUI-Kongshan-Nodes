from __future__ import annotations

from pathlib import Path

from ._cli_file_io_utils import _load_tensor, _resolve_image_path, _path_candidates, _latest_image


class KSCLIImageOutputFile:
    DESCRIPTION = "从 CLI 输出中定位生成图片并加载回 ComfyUI；优先使用期望路径，其次解析 stdout/stderr，最后可搜索目录最新图片。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "stdout": ("STRING", {"forceInput": True, "tooltip": "CLI 标准输出。节点会从中解析可能的图片路径，常用于工具打印保存路径的场景。"}),
                "stderr": ("STRING", {"forceInput": True, "tooltip": "CLI 标准错误。期望路径找不到时也会从这里解析图片路径，并在失败时展示错误片段。"}),
                "return_code": ("INT", {"forceInput": True, "tooltip": "CLI 退出码。非 0 且找不到图片时节点会报 CLI failed。"}),
                "expected_output_path": ("STRING", {"forceInput": True, "tooltip": "首选图片路径，通常来自 CLI 图片输入转临时文件节点的 output_path。找到后直接加载。"}),
            },
            "optional": {
                "working_directory": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "解析相对图片路径时使用的工作目录。留空使用当前 Python 工作目录。",
                    },
                ),
                "search_directory": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "兜底搜索目录。期望路径和输出文本都找不到图片时，节点会加载该目录中修改时间最新的图片。",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "output_path")
    RETURN_DESCRIPTIONS = (
        "加载回 ComfyUI 的生成图片。",
        "最终找到并加载的图片绝对路径。",
    )
    FUNCTION = "load"
    CATEGORY = "Kongshan/Local"

    def load(
        self,
        stdout,
        stderr,
        return_code,
        expected_output_path,
        working_directory="",
        search_directory="",
     ):
        working_dir_str = str(working_directory).strip()
        if working_dir_str.isdigit():
            print(f"[Warning] KSCLIImageOutputFile: working_directory '{working_dir_str}' is numeric. "
                  f"This is likely a widget value mismatch. Defaulting to current working directory.")
            working_dir_str = ""
        cwd = Path(working_dir_str).expanduser().resolve() if working_dir_str else Path.cwd()
        expected = Path(expected_output_path.strip()).expanduser()
        found = _resolve_image_path(expected, cwd) if expected_output_path.strip() else None

        combined_output = "\n".join([stdout or "", stderr or ""])
        if found is None:
            for candidate in _path_candidates(combined_output):
                found = _resolve_image_path(candidate, cwd)
                if found is not None:
                    break

        if found is None and search_directory.strip():
            found = _latest_image(Path(search_directory.strip()).expanduser())

        if found is None:
            detail = (combined_output.strip() or "CLI produced no stdout/stderr.")[:2000]
            if int(return_code) != 0:
                raise RuntimeError(
                    f"CLI failed with exit code {return_code} and produced no image.\n{detail}"
                )
            raise RuntimeError(
                "CLI finished but no generated image was found. "
                "Write the image to expected_output_path or print an image path.\n"
                f"{detail}"
            )

        return _load_tensor(found), str(found)


NODE_CLASS_MAPPINGS = {
    "KSCLIImageOutputFile": KSCLIImageOutputFile,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSCLIImageOutputFile": "CLI 输出文件转图片",
}
