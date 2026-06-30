# Kongshan Nodes

Kongshan Nodes is a ComfyUI custom-node package extracted from
`kongshan_comfyui_workspace`. It provides nodes for product-image workflows,
including Gemini/OpenRouter generation, local file IO, CLI execution, SAM,
SAM-HQ, GroundingDINO, mask utilities, white-background composition, and
directory-based image saving.

## Install

Install from ComfyUI Manager by adding this repository as a custom node source:

```text
https://github.com/kongshan4219/ComfyUI-Kongshan-Nodes.git
```

After the package is published to Comfy Registry, it can also be installed by
node id:

```powershell
comfy node install kongshan-nodes
```

## Project Structure

This repository follows the current ComfyUI custom-node scaffold layout:

```text
ComfyUI-Kongshan-Nodes/
├── __init__.py                  # ComfyUI custom_nodes entrypoint
├── pyproject.toml               # Registry and Python package metadata
├── src/py/                      # Python package loaded by the ComfyUI entrypoint
│   ├── api/                     # API-backed nodes and their HTTP route helpers
│   ├── cli/                     # CLI-backed nodes and their file IO helpers
│   └── local/                   # Local nodes plus bundled SAM-HQ/GroundingDINO code
└── web/                         # ComfyUI frontend extensions
```

Workflow files are intentionally not included in this repository. It is
published as a node-only registry package.

## Registry Metadata

This repository includes `pyproject.toml` metadata required by Comfy Registry
and ComfyUI Manager:

```toml
[project]
name = "kongshan-nodes"

[tool.comfy]
PublisherId = "kongshan4219"
DisplayName = "Kongshan Nodes"
```

Before publishing, confirm that `PublisherId` matches the publisher id created
on Comfy Registry.

Manual publishing:

```powershell
comfy node publish
```

Automated publishing:

1. Create a Comfy Registry access token.
2. Add it to this GitHub repository as an Actions secret named
   `REGISTRY_ACCESS_TOKEN`.
3. Run the `Publish ComfyUI Node` workflow manually, or push a version tag such
   as `v0.1.0`.

## Local Configuration

Copy `.env.example` to `.env` and fill local keys as needed:

```text
OPENROUTER_API_KEY=
OPENCODE_API_KEY=
Gemini_API_KEY_FREE=
GEMINI_API_KEY=
```

Never commit `.env`.

## Local File Pickers

The local image and directory nodes include UI buttons for selecting real
filesystem paths:

- `从原始路径加载图片` opens the browser file picker, uploads the selected image
  to ComfyUI's input directory, and loads it with a ComfyUI-style `[input]`
  path.
- `保存图片到自定义目录` opens a system directory picker for the output folder.

Image loading follows ComfyUI's built-in `LoadImage` behavior for EXIF
orientation, animated image frames, alpha masks, output dtype, and output
device placement, while still returning the original filesystem path for
downstream nodes.

The input-image picker follows ComfyUI's built-in `LoadImage` pattern: the
browser opens the native picker and uploads the selected file to the ComfyUI
input directory.

The output-directory picker asks the backend to choose a real filesystem
folder. On Linux, that backend picker uses `zenity`; on macOS, it uses the
native `osascript` folder chooser.

Output-directory picker dependency checks and install commands:

Debian/Ubuntu Linux:

```bash
sudo apt update
sudo apt install -y zenity
```

Fedora Linux:

```bash
sudo dnf install -y zenity
```

Arch Linux:

```bash
sudo pacman -S zenity
```

macOS:

```bash
osascript -e 'POSIX path of (choose folder with prompt "Select folder")'
```

No extra package is usually required on macOS.

## Included Node Groups

- `Kongshan/API`: product analysis, reference selection, design strategy, and
  Gemini/OpenRouter image generation.
- `Kongshan/CLI`: single-command Agent execution, including Antigravity/Codex
  style command runners.
- `Kongshan/Local`: local image loading, directory IO, SAM/GroundingDINO
  segmentation, masks, product crops, white-background composition, and
  size-chart arrow drawing.
