from __future__ import annotations

import re
from pathlib import Path

# Import to register API routes for selection
from . import _image_files_utils
from ._load_image_utils import image_file_hash, load_image_like_comfy


def natural_sort_key(path: Path) -> list:
    """Helper function to split path name into parts of numbers and non-numbers for natural sorting."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", path.name)]


class KSDirectoryImageSelector:
    DESCRIPTION = "从指定目录中过滤出所有图片，并根据索引加载其中一张，输出图片、遮罩、绝对路径及文件名。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "directory_path": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "要读取的图片目录路径。",
                    },
                ),
                "index": (
                    [""],
                    {
                        "default": "",
                        "tooltip": "要加载的源图片名。下拉框会自动读取目录中的图片文件。",
                    },
                ),
                "pattern": (
                    "STRING",
                    {
                        "default": "*.png, *.jpg, *.jpeg, *.webp, *.bmp",
                        "tooltip": "过滤文件后缀名，多个以逗号或分号分隔。留空时匹配所有支持的图片格式。",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "STRING", "INT")
    RETURN_NAMES = ("image", "mask", "source_image_path", "filename", "total_images")
    RETURN_DESCRIPTIONS = (
        "加载后的 RGB 图片张量。",
        "由透明通道生成的遮罩；无透明通道时输出全黑遮罩。",
        "选中图片的绝对路径，可连接到保存节点用于自动定位输出目录。",
        "选中图片的文件名（含后缀）。",
        "目录中匹配到的图片总数。",
    )
    FUNCTION = "load_image_from_dir"
    CATEGORY = "Kongshan/Local"

    @classmethod
    def IS_CHANGED(cls, directory_path, index, pattern):
        selected_file, _ = cls._resolve_selection(directory_path, index, pattern)
        if selected_file is None:
            return ""
        return image_file_hash(selected_file)

    @classmethod
    def VALIDATE_INPUTS(cls, directory_path, index, pattern):
        selected_file, error = cls._resolve_selection(directory_path, index, pattern)
        if error:
            return error
        if selected_file is None or not selected_file.is_file():
            return f"Invalid image file: {index}"
        return True

    @staticmethod
    def _resolve_directory(directory_path):
        path = Path(str(directory_path).strip()).expanduser()
        if path.is_dir():
            return path

        try:
            import folder_paths

            resolved = Path(folder_paths.get_annotated_filepath(str(directory_path)))
            if resolved.is_dir():
                return resolved
        except Exception:
            pass

        return path

    @staticmethod
    def _matching_files(directory_path, pattern):
        dir_path = KSDirectoryImageSelector._resolve_directory(directory_path)
        if not dir_path.is_dir():
            return None, [], f"Directory not found: {dir_path}"

        file_paths = [p for p in dir_path.iterdir() if p.is_file()]
        extensions = []
        if str(pattern).strip():
            parts = re.split(r"[,;]+", str(pattern))
            for p in parts:
                p_clean = p.strip().lower()
                if p_clean:
                    p_clean = p_clean.lstrip("*").lstrip(".")
                    if p_clean:
                        extensions.append("." + p_clean)
        if extensions:
            files = [p for p in file_paths if p.suffix.lower() in extensions]
        else:
            try:
                import folder_paths

                image_names = set(folder_paths.filter_files_content_types([p.name for p in file_paths], ["image"]))
                files = [p for p in file_paths if p.name in image_names]
            except Exception:
                fallback_extensions = [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"]
                files = [p for p in file_paths if p.suffix.lower() in fallback_extensions]

        files = sorted(files, key=natural_sort_key)
        return dir_path, files, ""

    @classmethod
    def _resolve_selection(cls, directory_path, index, pattern):
        dir_path, files, error = cls._matching_files(directory_path, pattern)
        if error:
            return None, error

        total = len(files)
        if total == 0:
            return None, f"No matching images found in directory: {dir_path}"

        index_text = str(index).strip()
        if not index_text:
            selected_file = files[0]
        else:
            name_text = re.split(r"[\\/]", index_text)[-1].lower()
            selected_file = next(
                (path for path in files if path.name.lower() == name_text),
                None,
            )
        if selected_file is None:
            available = ", ".join(path.name for path in files[:20])
            return None, (
                f"Image name not found in directory: {index_text}. "
                f"Available examples: {available}"
            )

        return selected_file, ""

    def load_image_from_dir(self, directory_path, index, pattern):
        selected_file, error = self._resolve_selection(directory_path, index, pattern)
        if error:
            raise RuntimeError(error)
        _, files, error = self._matching_files(directory_path, pattern)
        if error:
            raise RuntimeError(error)

        image_tensor, mask = load_image_like_comfy(selected_file)
        total = len(files)
        return (image_tensor, mask, str(selected_file.resolve()), selected_file.name, total)


NODE_CLASS_MAPPINGS = {
    "KSDirectoryImageSelector": KSDirectoryImageSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSDirectoryImageSelector": "目录图片选择加载器",
}
