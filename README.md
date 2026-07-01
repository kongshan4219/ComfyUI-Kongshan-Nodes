# Kongshan Nodes

Kongshan Nodes is a ComfyUI custom-node package extracted from
`kongshan_comfyui_workspace`. It provides nodes for product-image workflows,
including Gemini/OpenRouter generation, local file IO, CLI execution, SAM,
SAM-HQ, GroundingDINO, mask utilities, white/transparent background composition, and
directory-based image saving.

## Install

Install from ComfyUI Manager by adding this repository as a custom node source:

```text
https://github.com/kongshan4219/ComfyUI-Kongshan-Nodes.git
```

After the package is published to Comfy Registry, it can also be installed by
node id:

```text
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

```text
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

- `从原始路径加载图片` opens a backend system file dialog and keeps the
  selected real filesystem path.
- `保存图片到自定义目录` opens a system directory picker for the output folder.

Image loading follows ComfyUI's built-in `LoadImage` behavior for EXIF
orientation, animated image frames, alpha masks, output dtype, and output
device placement, while still returning the original filesystem path for
downstream nodes.

The input-image picker uses the backend system file dialog because browser file
inputs cannot expose absolute local paths. On Windows it opens the native
Explorer-style file dialog through Python `ctypes`; on Fedora/Linux it uses
`zenity` or `kdialog`.

The output-directory picker asks the backend to choose a real filesystem
folder through the same operating-system-specific backend.

Fedora/Linux picker dependency checks and install commands:

Fedora Linux:

```bash
sudo dnf install -y zenity
# or
sudo dnf install -y kdialog
```

No extra package is required on Windows.

## Included Node Groups

- `Kongshan/API`: product analysis, reference selection, design strategy, and
  Gemini/OpenRouter image generation.
- `Kongshan/CLI`: single-command Agent execution, including Antigravity/Codex
  style command runners.
- `Kongshan/Local`: local image loading, directory IO, SAM/GroundingDINO
  segmentation, masks, product crops, white/transparent background composition, and
  size-chart arrow drawing.
