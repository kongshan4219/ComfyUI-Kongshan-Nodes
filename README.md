# Kongshan Nodes

Kongshan Nodes is a ComfyUI custom-node package extracted from
`kongshan_comfyui_workspace`. It provides nodes for product-image workflows,
including Gemini/OpenRouter generation, local file IO, CLI execution, SAM,
SAM-HQ, GroundingDINO, mask utilities, white-background composition, and
directory-based image selection/saving.

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
├── src/nodes/                   # Flat directory containing all node modules and node loader
├── src/api/                     # ComfyUI HTTP routes used by frontend widgets
├── src/local_groundingdino/     # Bundled GroundingDINO support code
└── src/sam_hq/                  # Bundled SAM-HQ support code
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

## Included Node Groups

- `Kongshan/API`: product analysis, reference selection, design strategy, and
  Gemini/OpenRouter image generation.
- `Kongshan/CLI`: single-command Agent execution, including Antigravity/Codex
  style command runners.
- `Kongshan/Local`: local image loading, directory IO, SAM/GroundingDINO
  segmentation, masks, product crops, white-background composition, and
  size-chart arrow drawing.
