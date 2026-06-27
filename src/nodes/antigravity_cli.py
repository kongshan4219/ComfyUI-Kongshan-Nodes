from __future__ import annotations

import os
import subprocess
from pathlib import Path


class KSAntigravityCLIExecute:
    DESCRIPTION = "在指定工作目录执行 Antigravity 或其他 CLI 命令，并返回 stdout、stderr 和退出码。"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "command": (
                    "STRING",
                    {
                        "default": "agy --print \"Describe what you can do.\"",
                        "multiline": True,
                        "tooltip": "要执行的命令行。可使用上一节点拼好的 agy 命令；命令会通过 shell=True 执行。",
                    },
                ),
            },
            "optional": {
                "stdin": (
                    "STRING",
                    {
                        "forceInput": True,
                        "default": "",
                        "multiline": True,
                        "tooltip": "传给命令标准输入的文本。留空时不发送 stdin；连接提示词或 JSON 时可让 CLI 从 stdin 读取。",
                    },
                ),
                "working_directory": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "命令执行目录。留空使用当前 Python 工作目录；填写项目路径可让相对路径和工具配置按该目录解析。",
                    },
                ),
                "timeout_seconds": ("INT", {"default": 1800, "min": 1, "max": 86400, "tooltip": "命令最长运行秒数。数值越大越适合长时间生图；超时会终止并返回错误信息。"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("stdout", "stderr", "return_code")
    RETURN_DESCRIPTIONS = (
        "命令标准输出文本，通常包含工具结果或生成文件路径。",
        "命令标准错误文本，用于查看报错、警告和调试信息。",
        "进程退出码。0 通常表示成功，非 0 表示失败，-1 表示节点捕获到执行异常。",
    )
    FUNCTION = "execute"
    CATEGORY = "Kongshan/CLI"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def execute(
        self,
        command,
        stdin="",
        working_directory="",
        timeout_seconds=1800,
    ):
        working_dir_str = str(working_directory).strip()
        if working_dir_str.isdigit():
            print(f"[Warning] KSAntigravityCLIExecute: working_directory '{working_dir_str}' is numeric. "
                  f"This is likely a widget value mismatch (shifted timeout). Defaulting to current working directory.")
            working_dir_str = ""

        cwd_path = Path(working_dir_str).expanduser().resolve() if working_dir_str else Path.cwd()
        if not cwd_path.exists():
            raise RuntimeError(f"Working directory does not exist: {cwd_path}")
        if not cwd_path.is_dir():
            raise RuntimeError(f"Working directory is not a directory: {cwd_path}")

        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        gemini_bin = str(Path.home() / ".gemini" / "antigravity" / "bin")
        paths = env.get("PATH", "").split(os.pathsep)
        for path_dir in (local_bin, gemini_bin):
            if path_dir not in paths:
                paths.insert(0, path_dir)
        env["PATH"] = os.pathsep.join(paths)

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd_path),
                env=env,
                input=stdin if stdin else None,
                capture_output=True,
                text=True,
                timeout=int(timeout_seconds),
            )
            return result.stdout, result.stderr, result.returncode
        except Exception as error:
            return "", str(error), -1


NODE_CLASS_MAPPINGS = {
    "KSAntigravityCLIExecute": KSAntigravityCLIExecute,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KSAntigravityCLIExecute": "Antigravity CLI 命令执行",
}
