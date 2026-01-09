'use strict';

const vscode = require('vscode');
const { PythonBridge } = require('../services/pythonBridge');

class ChatPanel {
    static createOrShow(extensionUri) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : vscode.ViewColumn.One;

        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel.panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'nestifyChat',
            'Nestify Chat',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')],
            }
        );

        ChatPanel.currentPanel = new ChatPanel(panel, extensionUri);
    }

    static disposeAll() {
        if (ChatPanel.currentPanel) {
            ChatPanel.currentPanel.dispose();
            ChatPanel.currentPanel = undefined;
        }
    }

    constructor(panel, extensionUri) {
        this.panel = panel;
        this.extensionUri = extensionUri;
        this.bridge = undefined;
        this.disposables = [];
        this.bridgeDisposables = [];
        this.debugEnabled = false;
        this.workspacePath = undefined;
        this.pythonPath = undefined;

        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
        this.panel.webview.onDidReceiveMessage((message) => this.handleWebviewMessage(message), null, this.disposables);

        this.updateWebviewHtml();
        this.startBackend();
    }

    dispose() {
        ChatPanel.currentPanel = undefined;
        if (this.bridge) {
            this.disposeBridgeListeners();
            this.bridge.dispose();
            this.bridge = undefined;
        }
        while (this.disposables.length) {
            const disposable = this.disposables.pop();
            try {
                if (disposable) {
                    disposable.dispose();
                }
            } catch (err) {
                console.error('Failed to dispose resource', err);
            }
        }
        this.panel.dispose();
    }

    updateWebviewHtml() {
        const webview = this.panel.webview;
        const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, 'media', 'main.js'));
        const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, 'media', 'styles.css'));
        const nonce = getNonce();

        webview.html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource} https:; script-src 'nonce-${nonce}'; style-src ${webview.cspSource};">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="${styleUri}">
    <title>Nestify Chat</title>
</head>
<body>
    <div class="container">
        <header class="toolbar">
            <span id="status" class="status">Connecting…</span>
            <span id="spinner" class="spinner" style="display:none" aria-label="Loading"></span>
            <div class="actions">
                <button id="listTools" disabled>List Tools</button>
                <button id="newSession" disabled>New Session</button>
                <button id="reconnect">Reconnect</button>
            </div>
        </header>
        <main class="content">
            <section class="chat" id="chatLog"></section>
        </main>
        <footer class="composer">
            <select id="modeSelect" style="margin-right: 0.5em;">
                <option value="default" selected>Default</option>
                <option value="plan">Plan</option>
                <option value="ask">Ask</option>
            </select>
            <input type="text" id="messageInput" placeholder="Message the Codex agent" />
            <button id="sendButton" disabled>Send</button>
        </footer>
    </div>
    <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
    }

    async startBackend() {
        const config = vscode.workspace.getConfiguration('nestify');
        const configuredWorkspace = (config.get('workspacePath') || '').trim();
        this.workspacePath = configuredWorkspace || this.resolveWorkspacePath();
        this.pythonPath = (config.get('pythonPath') || 'python').trim() || 'python';

        this.setControlsEnabled(false);

        if (!this.workspacePath) {
            this.postToWebview({ type: 'status', level: 'error', message: 'Unable to determine workspace path. Set codexChat.workspacePath in settings.' });
            this.setControlsEnabled(false);
            return;
        }

            this.postToWebview({ type: 'status', level: 'info', message: `Starting Nestify backend in ${this.workspacePath}…` });

        if (this.bridge) {
            this.disposeBridgeListeners();
            this.bridge.dispose();
            this.bridge = undefined;
        }
        this.bridge = new PythonBridge();

        this.bridgeDisposables.push(this.bridge.onMessage((payload) => this.handleBridgeMessage(payload)));
        this.bridgeDisposables.push(this.bridge.onError((message) => this.postToWebview({ type: 'system', message })));
        this.bridgeDisposables.push(this.bridge.onExit(({ code, signal }) => {
            this.postToWebview({ type: 'status', level: 'warning', message: `Backend exited (code: ${code ?? 'null'}, signal: ${signal ?? 'null'}).` });
            this.setControlsEnabled(false);
        }));

        try {
            await this.bridge.start(this.workspacePath, this.pythonPath);
            this.postToWebview({ type: 'status', level: 'info', message: 'Backend process started. Waiting for ready event…' });
        } catch (error) {
            const message = error && error.message ? error.message : String(error);
            this.postToWebview({ type: 'status', level: 'error', message: `Failed to launch backend: ${message}` });
            this.setControlsEnabled(false);
        }
    }

    resolveWorkspacePath() {
        const folders = vscode.workspace.workspaceFolders;
        if (folders && folders.length > 0) {
            return folders[0].uri.fsPath;
        }
        const envPath = process.env.CODEX_AGENT_ROOT;
        if (envPath && envPath.trim().length > 0) {
            return envPath.trim();
        }
        return undefined;
    }

    async handleWebviewMessage(message) {
        if (!message || !message.type) {
            return;
        }

        switch (message.type) {
            case 'editor_query':
                console.log('[Codex Chat] Received editor_query request', message);
                this.handleEditorQuery(message).catch((error) => {
                    const errMsg = error && error.message ? error.message : String(error);
                    if (this.bridge && this.bridge.isRunning) {
                        this.bridge.send({ type: 'editor_query_response', id: message.id, error: errMsg }).catch(() => undefined);
                    }
                    this.postToWebview({ type: 'status', level: 'error', message: `Failed to service editor query: ${errMsg}` });
                    console.error('[Codex Chat] editor_query failed', errMsg);
                });
                break;
            case 'send': {
                if (!this.bridge || !this.bridge.isRunning) {
                    this.postToWebview({ type: 'status', level: 'error', message: 'Backend is not running. Click reconnect.' });
                    return;
                }
                const mode = message.mode || 'default';
                if (message.content && message.content.trim().length > 0) {
                    try {
                        await this.bridge.send({ type: 'message', content: message.content, mode });
                    } catch (error) {
                        this.postToWebview({ type: 'status', level: 'error', message: `Failed to send message: ${error.message || error}` });
                    }
                }
                break;
            }
            case 'shell_approval_response':
                // Relay shell approval response from webview to backend
                if (this.bridge && this.bridge.isRunning) {
                    this.bridge.send({
                        type: 'shell_approval_response',
                        id: message.id,
                        approved: message.approved,
                        approve_all: message.approve_all
                    }).catch((error) => {
                        this.postToWebview({ type: 'status', level: 'error', message: `Failed to send shell approval response: ${error.message || error}` });
                    });
                }
                break;
            // Removed debug toggle handling
                break;
            case 'listTools':
                if (this.bridge && this.bridge.isRunning) {
                    this.bridge.send({ type: 'message', content: '!tools' }).catch((error) => {
                        this.postToWebview({ type: 'status', level: 'error', message: `Failed to request tools: ${error.message || error}` });
                    });
                }
                break;
            case 'newSession':
                if (this.bridge && this.bridge.isRunning) {
                    this.bridge.send({ type: 'message', content: '!new' }).catch((error) => {
                        this.postToWebview({ type: 'status', level: 'error', message: `Failed to reset session: ${error.message || error}` });
                    });
                }
                break;
            case 'reconnect':
                await this.restartBackend();
                break;
            default:
                break;
        }
    }

    async restartBackend() {
        this.setControlsEnabled(false);
        this.postToWebview({ type: 'status', level: 'info', message: 'Restarting backend…' });
        if (this.bridge) {
            await this.bridge.stop().catch(() => undefined);
        }
        await this.startBackend();
    }

    handleBridgeMessage(message) {
        if (!message || !message.type) {
            return;
        }

        // Debug messages are now only logged to console
        if (typeof message.debug === 'boolean') {
            this.debugEnabled = message.debug;
        }
        if (Array.isArray(message.debug) && message.debug.length > 0) {
            message.debug.forEach((line) => {
                console.log('[Codex Chat][DEBUG]', line);
            });
        }

        if (Array.isArray(message.extras) && message.extras.length > 0) {
            message.extras.forEach((line) => {
                this.postToWebview({ type: 'system', message: line });
            });
        }

        switch (message.type) {
            case 'shell_approval_request':
                // Relay shell approval request to webview
                this.postToWebview({
                    type: 'shell_approval_request',
                    command: message.command,
                    reason: message.reason,
                    approveAll: message.approveAll,
                    id: message.id
                });
                break;
            case 'editor_query':
                console.log('[Codex Chat] handleBridgeMessage received editor_query', message);
                this.handleEditorQuery(message).catch((error) => {
                    const errMsg = error && error.message ? error.message : String(error);
                    console.error('[Codex Chat] Failed to service editor_query in handleBridgeMessage', errMsg);
                    if (this.bridge && this.bridge.isRunning) {
                        this.bridge.send({ type: 'editor_query_response', id: message.id, error: errMsg }).catch(() => undefined);
                    }
                });
                break;
            case 'ready':
                this.setControlsEnabled(true);
                this.postToWebview({ type: 'status', level: 'info', message: 'Backend ready. Say hello!' });
                this.postToWebview({ type: 'spinner', show: false });
                break;
            case 'assistant_stream':
                this.postToWebview({ type: 'assistant_stream', message: message.content || '' });
                break;
            case 'assistant_final':
                this.postToWebview({ type: 'assistant_final', message: message.content || '' });
                this.postToWebview({ type: 'spinner', show: false });
                this.setControlsEnabled(true);
                break;
            case 'assistant':
                this.postToWebview({ type: 'assistant', message: message.content || '' });
                break;
            case 'notification':
                this.postToWebview({ type: 'system', message: message.content || '' });
                break;
            case 'error':
                this.postToWebview({ type: 'status', level: 'error', message: message.content || 'Unknown backend error.' });
                break;
            default:
                if (message.content) {
                    this.postToWebview({ type: 'system', message: message.content });
                }
                break;
        }
    }

    postToWebview(payload) {
        try {
            this.panel.webview.postMessage(payload);
        } catch (err) {
            console.error('Failed to post message to webview', err);
        }
    }

    setControlsEnabled(enabled) {
        this.postToWebview({ type: 'controls', enabled });
    }

    disposeBridgeListeners() {
        while (this.bridgeDisposables.length) {
            const disposable = this.bridgeDisposables.pop();
            if (disposable && typeof disposable.dispose === 'function') {
                try {
                    disposable.dispose();
                } catch (err) {
                    console.error('Failed to dispose listener', err);
                }
            }
        }
    }

    async handleEditorQuery(message) {
        if (!message || !message.id || !message.query) {
            throw new Error('Invalid editor query message.');
        }
        if (!this.bridge || !this.bridge.isRunning) {
            throw new Error('Backend bridge is not running.');
        }

        const payload = message.payload || {};
        let result;
        switch (message.query) {
            case 'diagnostics':
                result = this.collectDiagnostics(payload);
                break;
            case 'open_editors':
                result = this.collectOpenEditors();
                break;
            case 'workspace_info':
                result = this.collectWorkspaceInfo();
                break;
            case 'document_symbols':
                result = await this.collectDocumentSymbols(payload);
                break;
            default:
                throw new Error(`Unknown editor query '${message.query}'.`);
        }

        await this.bridge.send({ type: 'editor_query_response', id: message.id, result });
        console.log('[Codex Chat] Sent editor_query_response', message.id);
    }

    collectDiagnostics(payload) {
        const options = typeof payload === 'object' && payload ? payload : {};
        const pathFilterRaw = typeof options.path === 'string' ? options.path.trim() : '';
        const severityFilterRaw = typeof options.severity === 'string' ? options.severity.trim().toLowerCase() : '';
        const limit = Number.isInteger(options.limit) && options.limit > 0 ? Math.min(options.limit, 500) : 200;
        const includeEmpty = options.includeEmpty === true;

        const normPathFilter = pathFilterRaw ? pathFilterRaw.replace(/\\/g, '/').toLowerCase() : '';

        const entries = [];
        const counts = { error: 0, warning: 0, information: 0, hint: 0 };
        let total = 0;
        let collected = 0;

        const severityMatches = (severity) => (!severityFilterRaw || severity === severityFilterRaw);

        for (const [uri, diagnostics] of vscode.languages.getDiagnostics()) {
            const matchesPath = this.pathMatches(uri, normPathFilter);
            if (!matchesPath && normPathFilter) {
                continue;
            }

            if (!Array.isArray(diagnostics) || diagnostics.length === 0) {
                if (includeEmpty && matchesPath) {
                    entries.push({ uri: uri.fsPath, diagnostics: [] });
                }
                continue;
            }

            const collectedDiagnostics = [];
            for (const diagnostic of diagnostics) {
                const severity = this.diagnosticSeverityToString(diagnostic.severity);
                if (!severityMatches(severity)) {
                    continue;
                }

                total += 1;
                counts[severity] = (counts[severity] || 0) + 1;

                if (collected < limit) {
                    collectedDiagnostics.push(this.toDiagnosticObject(uri, diagnostic, severity));
                    collected += 1;
                }
            }

            if (collectedDiagnostics.length > 0) {
                entries.push({
                    uri: uri.fsPath,
                    diagnostics: collectedDiagnostics,
                });
            } else if (includeEmpty && matchesPath) {
                entries.push({ uri: uri.fsPath, diagnostics: [] });
            }

            if (collected >= limit) {
                break;
            }
        }

        const response = {
            summary: counts,
            returned: collected,
            total,
            truncated: total > collected,
            items: entries,
            limit,
        };
        console.log('[Codex Chat] collectDiagnostics result', response.summary, `returned=${response.returned}`, `total=${response.total}`);
        return response;
    }

    collectOpenEditors() {
        const editors = vscode.window.visibleTextEditors || [];
        const active = vscode.window.activeTextEditor;
        return editors.map((editor) => ({
            uri: editor.document ? editor.document.uri.fsPath : undefined,
            languageId: editor.document ? editor.document.languageId : undefined,
            isDirty: editor.document ? editor.document.isDirty : false,
            isActive: active ? editor.document === active.document : false,
            selections: editor.selections ? editor.selections.map((sel) => ({
                start: { line: sel.start.line + 1, character: sel.start.character + 1 },
                end: { line: sel.end.line + 1, character: sel.end.character + 1 },
            })) : [],
        }));
    }

    collectWorkspaceInfo() {
        const folders = vscode.workspace.workspaceFolders || [];
        const configurationTarget = vscode.ConfigurationTarget ? 'workspace' : undefined;
        return {
            workspaceFolders: folders.map((folder) => ({
                name: folder.name,
                path: folder.uri.fsPath,
            })),
            activeFile: vscode.window.activeTextEditor && vscode.window.activeTextEditor.document
                ? vscode.window.activeTextEditor.document.uri.fsPath
                : undefined,
            configurationTarget,
        };
    }

    async collectDocumentSymbols(payload) {
        const options = typeof payload === 'object' && payload ? payload : {};
        const path = typeof options.path === 'string' ? options.path.trim() : '';
        let targetUri;
        if (path) {
            targetUri = this.resolveUri(path);
        } else if (vscode.window.activeTextEditor) {
            targetUri = vscode.window.activeTextEditor.document.uri;
        }
        if (!targetUri) {
            throw new Error('No target document available for symbol lookup.');
        }

        const symbols = await vscode.commands.executeCommand('vscode.executeDocumentSymbolProvider', targetUri);
        if (!symbols || symbols.length === 0) {
            return { uri: targetUri.fsPath, symbols: [] };
        }

        const normalize = (symbol) => {
            if (!symbol) {
                return undefined;
            }
            const convertRange = (range) => ({
                start: { line: range.start.line + 1, character: range.start.character + 1 },
                end: { line: range.end.line + 1, character: range.end.character + 1 },
            });
            const entry = {
                name: symbol.name,
                detail: symbol.detail || '',
                kind: this.symbolKindToString(symbol.kind),
                range: convertRange(symbol.range),
                selectionRange: convertRange(symbol.selectionRange || symbol.range),
            };
            if (Array.isArray(symbol.children) && symbol.children.length > 0) {
                entry.children = symbol.children.map(normalize).filter(Boolean);
            }
            return entry;
        };

        return {
            uri: targetUri.fsPath,
            symbols: symbols.map(normalize).filter(Boolean),
        };
    }

    pathMatches(uri, normPathFilter) {
        if (!uri || !uri.fsPath) {
            return false;
        }
        if (!normPathFilter) {
            return true;
        }
        const fsPath = uri.fsPath.replace(/\\/g, '/').toLowerCase();
        return fsPath === normPathFilter
            || fsPath.endsWith(normPathFilter)
            || fsPath.includes(normPathFilter);
    }

    toDiagnosticObject(uri, diagnostic, severity) {
        return {
            file: uri.fsPath,
            message: diagnostic.message,
            source: diagnostic.source || '',
            code: diagnostic.code || '',
            severity,
            range: {
                start: { line: diagnostic.range.start.line + 1, character: diagnostic.range.start.character + 1 },
                end: { line: diagnostic.range.end.line + 1, character: diagnostic.range.end.character + 1 },
            },
        };
    }

    diagnosticSeverityToString(severity) {
        switch (severity) {
            case vscode.DiagnosticSeverity.Error:
                return 'error';
            case vscode.DiagnosticSeverity.Warning:
                return 'warning';
            case vscode.DiagnosticSeverity.Information:
                return 'information';
            case vscode.DiagnosticSeverity.Hint:
                return 'hint';
            default:
                return 'unknown';
        }
    }

    symbolKindToString(kind) {
        const SymbolKind = vscode.SymbolKind;
        for (const key of Object.keys(SymbolKind)) {
            if (SymbolKind[key] === kind) {
                return key.toLowerCase();
            }
        }
        return 'unknown';
    }

    resolveUri(inputPath) {
        if (!inputPath) {
            return undefined;
        }
        const folders = vscode.workspace.workspaceFolders || [];
        for (const folder of folders) {
            const candidate = vscode.Uri.joinPath(folder.uri, inputPath);
            if (vscode.workspace.fs) {
                // We cannot synchronously check existence; return first candidate.
                return candidate;
            }
        }
        try {
            return vscode.Uri.file(inputPath);
        } catch (err) {
            return undefined;
        }
    }
}

ChatPanel.currentPanel = undefined;

function getNonce() {
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let text = '';
    for (let i = 0; i < 32; i += 1) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}

module.exports = {
    ChatPanel,
};
