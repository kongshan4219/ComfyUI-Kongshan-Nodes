import { app } from "/scripts/app.js";

const NODE_ALIASES = {
    KSDirectorySaveImages: ["KSDirectorySaveImages", "目录保存图片"],
    KSLoadImageWithPath: ["KSLoadImageWithPath", "从原始路径加载图片"],
};

const resolveNodeName = (nodeData) => {
    const names = [
        nodeData.name,
        nodeData.display_name,
        nodeData.displayName,
        nodeData.title,
    ].filter(Boolean);

    for (const [nodeName, aliases] of Object.entries(NODE_ALIASES)) {
        if (aliases.some((alias) => names.includes(alias))) {
            return nodeName;
        }
    }
    return "";
};

const addButton = (node, label, callback) => {
    const button = node.addWidget("button", label, "", callback);
    button.serialize = false;
    return button;
};

app.registerExtension({
    name: "Kongshan.ProductSplit.DirectoryPicker",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const nodeName = resolveNodeName(nodeData);
        if (!nodeName) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            if (nodeName === "KSLoadImageWithPath") {
                addButton(this, "选择图片文件", async () => {
                    const imagePathWidget = this.widgets?.find(
                        (widget) => widget.name === "image_path"
                    );
                    if (!imagePathWidget) return;

                    try {
                        const response = await fetch("/ks-product-split/select-image-file", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ initial_path: imagePathWidget.value || "" }),
                        });
                        const payload = await response.json();
                        if (!response.ok) {
                            app.ui.dialog.show(payload.error || "图片选择器启动失败");
                            return;
                        }
                        if (!payload.cancelled && payload.path) {
                            imagePathWidget.value = payload.path;
                            imagePathWidget.callback?.(payload.path);
                            this.setDirtyCanvas(true, true);
                        }
                    } catch (error) {
                        app.ui.dialog.show(error.message || "图片选择器启动失败");
                    }
                });
                return result;
            }

            addButton(this, "选择输出目录", async () => {
                const directoryWidget = this.widgets?.find(
                    (widget) => widget.name === "output_directory"
                );
                if (!directoryWidget) return;

                const response = await fetch("/ks-product-split/select-directory", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ initial_directory: directoryWidget.value || "" }),
                });
                const payload = await response.json();
                if (!response.ok) {
                    app.ui.dialog.show(payload.error || "目录选择器启动失败");
                    return;
                }
                if (!payload.cancelled && payload.path) {
                    directoryWidget.value = payload.path;
                    directoryWidget.callback?.(payload.path);
                    this.setDirtyCanvas(true, true);
                }
            });
            return result;
        };
    },
});

