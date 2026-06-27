import { app } from "/scripts/app.js";

const TARGET_NODES = {
    "KSAnalyzeProduct": "vlm",
    "KSSelectReference": "embedding",
    "KSDesignStrategy": "vlm",
    "KSGeminiGenerate": "image_gen"
};

app.registerExtension({
    name: "Kongshan.AI.APIModels",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const category = TARGET_NODES[nodeData.name];
        if (!category) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            const node = this;

            const configPathWidget = node.widgets?.find((w) => w.name === "config_path");
            const providerWidget = node.widgets?.find((w) => w.name === "provider");
            const apiKeyWidget = node.widgets?.find((w) => w.name === "api_key");
            const modelWidget = node.widgets?.find((w) => w.name === "model");

            if (!configPathWidget || !providerWidget || !apiKeyWidget || !modelWidget) {
                return result;
            }

            node.modelRequestId = 0;
            node.configInfo = null;

            const updateWidgetOptions = (widget, options, keepValue = false) => {
                if (!widget) return;
                widget.type = "combo";
                const widgetValues = widget.options?.values;
                if (Array.isArray(widgetValues)) {
                    widgetValues.splice(0, widgetValues.length, ...options);
                } else {
                    widget.options = { ...widget.options, values: [...options] };
                }

                const inputName = widget.name;
                const requiredConfig = nodeData.input?.required?.[inputName]?.[0];
                if (Array.isArray(requiredConfig) && requiredConfig !== widgetValues) {
                    requiredConfig.splice(0, requiredConfig.length, ...options);
                }
                const inputOptions = nodeData.inputs?.[inputName]?.options;
                if (Array.isArray(inputOptions) && inputOptions !== widgetValues) {
                    inputOptions.splice(0, inputOptions.length, ...options);
                }

                let matchedValue = widget.value;
                if (widget.value === "default" || widget.value?.startsWith("default (") || widget.value?.startsWith("default(")) {
                    const defaultOpt = options.find(opt => opt === "default" || opt.startsWith("default (") || opt.startsWith("default("));
                    if (defaultOpt) {
                        matchedValue = defaultOpt;
                    }
                }

                if (!options.includes(matchedValue)) {
                    if (!keepValue) {
                        widget.value = options[0];
                        widget.callback?.(widget.value);
                    }
                } else {
                    widget.value = matchedValue;
                }
            };

            const refreshModels = async (showError = false, keepValue = false) => {
                const configPath = configPathWidget.value;
                const selectedProvider = providerWidget.value;
                const selectedApiKey = apiKeyWidget.value;
                const currentRequest = ++node.modelRequestId;

                try {
                    const response = await fetch("/ks-nodes/models", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            config_path: configPath,
                            provider: selectedProvider,
                            api_key: selectedApiKey,
                            category: category
                        })
                    });
                    const payload = await response.json();
                    if (!response.ok) throw new Error(payload.error || "Failed to load models");
                    if (currentRequest !== node.modelRequestId) return;

                    const configData = node.configInfo;
                    let defaultModelName = configData?.defaults?.[category]?.model || "";
                    const defaultLabel = defaultModelName ? `default (${defaultModelName})` : "default";

                    const models = [defaultLabel, ...(payload.models || [])];
                    updateWidgetOptions(modelWidget, models, keepValue);
                    node.setDirtyCanvas(true, true);
                } catch (error) {
                    console.warn("[Kongshan Nodes] Model refresh failed:", error);
                    if (showError) app.ui.dialog.show(error.message || String(error));
                }
            };

            const refreshApiKeys = async (showError = false, keepValue = false) => {
                const payload = node.configInfo;
                if (!payload) return;

                let selectedProvider = providerWidget.value;
                if (selectedProvider === "default" || selectedProvider?.startsWith("default (") || selectedProvider?.startsWith("default(")) {
                    selectedProvider = payload.defaults?.[category]?.provider || "";
                }

                const providerData = payload.providers?.[selectedProvider] || {};
                const apiKeys = (providerData.api_keys || []).map(k => k.name);

                let defaultKeyName = payload.defaults?.[category]?.api_key || "default";
                if (defaultKeyName === "default" || defaultKeyName?.startsWith("default (") || defaultKeyName?.startsWith("default(")) {
                    defaultKeyName = providerData.default_api_key || "";
                }
                const defaultLabel = defaultKeyName ? `default (${defaultKeyName})` : "default";
                const apiKeyOptions = [defaultLabel, ...apiKeys];

                updateWidgetOptions(apiKeyWidget, apiKeyOptions, keepValue);
                await refreshModels(showError, keepValue);
            };

            const refreshConfigAndProviders = async (showError = false, keepValue = false) => {
                const configPath = configPathWidget.value;
                try {
                    const response = await fetch("/ks-nodes/config-info", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ config_path: configPath }),
                    });
                    const payload = await response.json();
                    if (!response.ok) throw new Error(payload.error || "Failed to load config info");

                    node.configInfo = payload;

                    const providers = Object.keys(payload.providers || {});
                    const defaultProvider = payload.defaults?.[category]?.provider || "";
                    const defaultLabel = defaultProvider ? `default (${defaultProvider})` : "default";
                    const providerOptions = [defaultLabel, ...providers];
                    updateWidgetOptions(providerWidget, providerOptions, keepValue);

                    await refreshApiKeys(showError, keepValue);
                } catch (error) {
                    console.warn("[Kongshan Nodes] Config info refresh failed:", error);
                    if (showError) app.ui.dialog.show(error.message || String(error));
                }
            };

            // Setup callbacks
            const originalConfigCallback = configPathWidget.callback;
            configPathWidget.callback = function (value) {
                const callbackResult = originalConfigCallback?.apply(this, arguments);
                refreshConfigAndProviders(true, false);
                return callbackResult;
            };

            const originalProviderCallback = providerWidget.callback;
            providerWidget.callback = function (value) {
                const callbackResult = originalProviderCallback?.apply(this, arguments);
                refreshApiKeys(true, false);
                return callbackResult;
            };

            const originalApiKeyCallback = apiKeyWidget.callback;
            apiKeyWidget.callback = function (value) {
                const callbackResult = originalApiKeyCallback?.apply(this, arguments);
                refreshModels(true, false);
                return callbackResult;
            };

            const refreshWidget = node.addWidget(
                "button",
                "刷新模型列表",
                null,
                () => refreshModels(true, false),
            );
            refreshWidget.serialize = false;

            node.refreshConfigAndProviders = refreshConfigAndProviders;

            // Trigger initial load keeping restored values
            setTimeout(() => refreshConfigAndProviders(false, true), 0);
            return result;
        };

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = originalConfigure?.apply(this, arguments);
            setTimeout(() => this.refreshConfigAndProviders?.(false, true), 0);
            return result;
        };
    }
});
