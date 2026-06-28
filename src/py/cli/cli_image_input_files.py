from __future__ import annotations

import time
import re
from pathlib import Path

import folder_paths
from ._cli_file_io_utils import _save_tensor_png, IMAGE_EXTENSIONS


class KSCLIImageInputFiles:
    DESCRIPTION = "把 ComfyUI 图片和提示词写入临时文件，并生成可交给外部 CLI 执行的命令。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "command_template": (
                    "STRING",
                    {
                        "default": (
                            "agy --print \"Create exactly one final e-commerce product image. "
                            "Use product image: {image_path}. Use reference image if provided: {reference_path}. "
                            "Read the detailed design prompt from: {prompt_path}. "
                            "Save the final image as a PNG file exactly at: {output_path}. "
                            "After saving, print only the saved image path.\""
                        ),
                        "multiline": True,
                        "tooltip": "命令模板。可使用 {prompt_path}、{image_path}、{reference_path}、{output_dir}、{output_path} 占位符，节点会替换成实际路径。",
                    },
                ),
                "prompt": ("STRING", {"forceInput": True, "tooltip": "写入临时 txt 的完整提示词。外部 CLI 可通过 {prompt_path} 读取。"}),
                "image": ("IMAGE", {"tooltip": "写入临时 PNG 的商品图。外部 CLI 可通过 {image_path} 读取。"}),
                "output_directory": (
                    "STRING",
                    {
                        "default": "image_pipeline/antigravity_cli",
                        "multiline": False,
                        "tooltip": "期望输出目录。相对路径会放在 ComfyUI output 目录下；绝对路径会直接使用。留空且连接 source_image_path 时，保存到 white_background 同级的 1688_main。",
                    },
                ),
                "output_filename": (
                    "STRING",
                    {
                        "default": "antigravity_result.png",
                        "multiline": False,
                        "tooltip": "期望输出文件名。填写时节点会保留扩展名并追加时间戳；留空且连接 source_image_path 时，使用源图片名并把 white_background 替换为 1688_main。",
                    },
                ),
            },
            "optional": {
                "reference_image": ("IMAGE", {"tooltip": "直接连接的参考图，会写入临时 PNG 并作为 {reference_path}。优先级高于 reference。"}),
                "reference": ("KS_REFERENCE", {"tooltip": "参考对象。若包含 image 会写入临时 PNG；否则使用其中 path 作为 {reference_path}。"}),
                "source_image_path": ("STRING", {"forceInput": True, "tooltip": "源图片路径。output_directory 留空时用它推导输出目录；output_filename 留空时用源图片名派生输出文件名。"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("command", "output_path", "prompt_path", "image_path", "reference_path")
    RETURN_DESCRIPTIONS = (
        "替换占位符后的完整命令，可连接到 CLI 执行节点。",
        "期望生成图片路径，可连接到 CLI 输出文件转图片节点。",
        "临时提示词文件路径。",
        "临时商品图文件路径。",
        "参考图路径；没有参考图时为空字符串。",
    )
    FUNCTION = "prepare"
    CATEGORY = "Kongshan/CLI"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def prepare(
        self,
        command_template,
        prompt,
        image,
        output_directory,
        output_filename,
        reference_image=None,
        reference=None,
        source_image_path="",
    ):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        temp_dir = Path(folder_paths.get_temp_directory())
        temp_dir.mkdir(parents=True, exist_ok=True)

        prompt_path = temp_dir / f"ks_cli_prompt_{stamp}.txt"
        prompt_path.write_text(prompt if prompt is not None else "", encoding="utf-8")
        image_path = temp_dir / f"ks_cli_input_{stamp}.png"
        _save_tensor_png(image, image_path)

        reference_path = ""
        if reference_image is not None:
            path = temp_dir / f"ks_cli_ref_{stamp}.png"
            reference_path = _save_tensor_png(reference_image, path)
        elif reference is not None and isinstance(reference, dict):
            if reference.get("image") is not None:
                path = temp_dir / f"ks_cli_ref_{stamp}.png"
                reference_path = _save_tensor_png(reference["image"], path)
            else:
                reference_path = str(reference.get("path", ""))

        output_root = Path(folder_paths.get_output_directory()).resolve()
        output_dir_text = str(output_directory).strip()
        source_path_text = str(source_image_path).strip()
        if output_dir_text:
            output_dir = Path(output_dir_text).expanduser()
        elif source_path_text:
            source_path = Path(source_path_text).expanduser()
            source_parent = source_path.parent
            if source_parent.name.lower() == "white_background":
                output_dir = source_parent.parent / "1688_main"
            else:
                output_dir = source_parent / "1688_main"
        else:
            output_dir = Path("image_pipeline/antigravity_cli")
        if not output_dir.is_absolute():
            output_dir = output_root / output_dir
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        output_filename_text = str(output_filename).strip()
        use_exact_filename = False
        if output_filename_text:
            filename = Path(output_filename_text).name
        elif source_path_text:
            source_name = Path(source_path_text).name
            filename = re.sub("white_background", "1688_main", source_name, flags=re.I)
            use_exact_filename = True
        else:
            filename = "antigravity_result.png"

        if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
            filename += ".png"
        if use_exact_filename:
            output_path = output_dir / filename
        else:
            output_path = output_dir / f"{Path(filename).stem}_{stamp}{Path(filename).suffix}"

        replacements = {
            "prompt_path": str(prompt_path),
            "image_path": str(image_path),
            "reference_path": reference_path,
            "output_dir": str(output_dir),
            "output_path": str(output_path),
        }
        command = command_template
        for key, value in replacements.items():
            command = command.replace(f"{{{key}}}", value)

        return command, str(output_path), str(prompt_path), str(image_path), reference_path


NODE_CLASS_MAPPINGS = {
    "KSCLIImageInputFiles": KSCLIImageInputFiles,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSCLIImageInputFiles": "CLI 图片输入转临时文件",
}
