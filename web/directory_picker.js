import { app } from "/scripts/app.js";

const NODE_ALIASES = {
    KSDirectorySaveImages: ["KSDirectorySaveImages", "目录保存图片"],
    KSLoadImageWithPath: ["KSLoadImageWithPath", "从原始路径加载图片"],
    KSDirectoryImageSelector: ["KSDirectoryImageSelector", "目录图片选择加载器"],
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

        const updateWidgetOptions = (node, widget, options, keepValue = false) => {
            if (!widget) return;
            widget.type = "combo";
            const values = options.length ? options : [""];
            const widgetValues = widget.options?.values;
            if (Array.isArray(widgetValues)) {
                widgetValues.splice(0, widgetValues.length, ...values);
            } else {
                widget.options = { ...widget.options, values: [...values] };
            }

            const inputName = widget.name;
            const requiredConfig = nodeData.input?.required?.[inputName]?.[0];
            if (Array.isArray(requiredConfig) && requiredConfig !== widgetValues) {
                requiredConfig.splice(0, requiredConfig.length, ...values);
            }
            const inputOptions = nodeData.inputs?.[inputName]?.options;
            if (Array.isArray(inputOptions) && inputOptions !== widgetValues) {
                inputOptions.splice(0, inputOptions.length, ...values);
            }

            if (!values.includes(widget.value)) {
                if (!keepValue || !widget.value) {
                    widget.value = values[0];
                    widget.callback?.(widget.value);
                }
            }
            node.setDirtyCanvas(true, true);
        };

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

            if (nodeName === "KSDirectoryImageSelector") {
                const node = this;
                const directoryWidget = node.widgets?.find((widget) => widget.name === "directory_path");
                const indexWidget = node.widgets?.find((widget) => widget.name === "index");
                const patternWidget = node.widgets?.find((widget) => widget.name === "pattern");

                node.refreshImageChoices = async (showError = false, keepValue = false) => {
                    if (!directoryWidget || !indexWidget || !patternWidget) return;
                    try {
                        const response = await fetch("/ks-product-split/list-images", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                directory_path: directoryWidget.value || "",
                                pattern: patternWidget.value || "",
                            }),
                        });
                        const payload = await response.json();
                        if (!response.ok) throw new Error(payload.error || "图片列表读取失败");
                        updateWidgetOptions(node, indexWidget, payload.images || [], keepValue);
                    } catch (error) {
                        console.warn("[Kongshan Nodes] Image list refresh failed:", error);
                        updateWidgetOptions(node, indexWidget, [], keepValue);
                        if (showError) app.ui.dialog.show(error.message || String(error));
                    }
                };

                const originalDirectoryCallback = directoryWidget?.callback;
                if (directoryWidget) {
                    directoryWidget.callback = function () {
                        const callbackResult = originalDirectoryCallback?.apply(this, arguments);
                        node.refreshImageChoices?.(true, false);
                        return callbackResult;
                    };
                }

                const originalPatternCallback = patternWidget?.callback;
                if (patternWidget) {
                    patternWidget.callback = function () {
                        const callbackResult = originalPatternCallback?.apply(this, arguments);
                        node.refreshImageChoices?.(true, false);
                        return callbackResult;
                    };
                }

                addButton(this, "选择输入目录", async () => {
                    if (!directoryWidget) return;

                    try {
                        const response = await fetch("/ks-product-split/select-directory", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ initial_directory: directoryWidget.value || "" }),
                        });
                        const payload = await response.json();
                        if (!response.ok) {
                            throw new Error(payload.error || "目录选择器启动失败");
                        }
                        if (payload.cancelled || !payload.path) return;

                        directoryWidget.value = payload.path;
                        directoryWidget.callback?.(payload.path);
                        await node.refreshImageChoices?.(true, false);
                        node.setDirtyCanvas(true, true);
                    } catch (error) {
                        app.ui.dialog.show(error.message || "目录选择器启动失败");
                    }
                });

                addButton(this, "刷新图片列表", () => {
                    node.refreshImageChoices?.(true, false);
                });

                setTimeout(() => node.refreshImageChoices?.(false, true), 0);
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

        if (nodeName === "KSDirectoryImageSelector") {
            const originalConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                const result = originalConfigure?.apply(this, arguments);
                setTimeout(() => this.refreshImageChoices?.(false, true), 0);
                return result;
            };
        }
    },
});

