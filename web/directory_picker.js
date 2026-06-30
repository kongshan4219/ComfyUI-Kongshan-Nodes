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

const pickFiles = () =>
    new Promise((resolve) => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "image/*";
        input.style.display = "none";
        input.addEventListener(
            "change",
            () => {
                const files = Array.from(input.files || []);
                input.remove();
                resolve(files);
            },
            { once: true }
        );
        document.body.append(input);
        input.click();
    });

const uploadImage = async (file, subfolder = "") => {
    const body = new FormData();
    body.append("image", file, file.name);
    body.append("type", "input");
    if (subfolder) body.append("subfolder", subfolder);

    const response = await fetch("/upload/image", {
        method: "POST",
        body,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "图片上传失败");
    return payload;
};

const annotatedInputPath = ({ name, subfolder }) => {
    const parts = [subfolder, name].filter(Boolean);
    return `${parts.join("/")} [input]`;
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
                        const files = await pickFiles();
                        const file = files[0];
                        if (!file) return;
                        const payload = await uploadImage(file, "kongshan_uploads");
                        const path = annotatedInputPath(payload);
                        imagePathWidget.value = path;
                        imagePathWidget.callback?.(path);
                        this.setDirtyCanvas(true, true);
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

