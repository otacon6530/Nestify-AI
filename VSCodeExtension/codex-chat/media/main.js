'use strict';

(function () {
    const vscode = acquireVsCodeApi();

    // Modal for shell approval
    let shellApprovalResolve = null;
    function showShellApprovalDialog(command, id, reason) {
        let modal = document.getElementById('shell-approval-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'shell-approval-modal';
            modal.style.position = 'fixed';
            modal.style.top = '0';
            modal.style.left = '0';
            modal.style.width = '100vw';
            modal.style.height = '100vh';
            modal.style.background = 'rgba(0,0,0,0.4)';
            modal.style.display = 'flex';
            modal.style.alignItems = 'center';
            modal.style.justifyContent = 'center';
            modal.style.zIndex = '9999';
            modal.innerHTML = `
                <div style="background: var(--vscode-editor-background, #222); color: var(--vscode-editor-foreground, #fff); padding: 2em; border-radius: 8px; min-width: 320px; max-width: 90vw; box-shadow: 0 2px 16px #0008;">
                    <h3>Approve Shell Command</h3>
                    <div style="margin-bottom: 1em; word-break: break-all;"><code id="shell-approval-command"></code></div>
                    <div id="shell-approval-reason" style="margin-bottom: 1em; font-size: 0.9em; opacity: 0.8;"></div>
                    <div style="display: flex; gap: 0.5em; justify-content: flex-end;">
                        <button id="shell-approve">Approve</button>
                        <button id="shell-approve-all">Approve All for Session</button>
                        <button id="shell-deny">Deny</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        modal.querySelector('#shell-approval-command').textContent = command;
        const reasonEl = modal.querySelector('#shell-approval-reason');
        if (reason && reasonEl) {
            reasonEl.textContent = reason;
            reasonEl.style.display = '';
        } else if (reasonEl) {
            reasonEl.textContent = '';
            reasonEl.style.display = 'none';
        }
        modal.style.display = 'flex';
        setSendEnabled(false);
        function cleanup() {
            modal.style.display = 'none';
            shellApprovalResolve = null;
            setSendEnabled(true);
        }
        modal.querySelector('#shell-approve').onclick = () => {
            vscode.postMessage({ type: 'shell_approval_response', id, approved: true, approve_all: false });
            cleanup();
        };
        modal.querySelector('#shell-approve-all').onclick = () => {
            vscode.postMessage({ type: 'shell_approval_response', id, approved: true, approve_all: true });
            cleanup();
        };
        modal.querySelector('#shell-deny').onclick = () => {
            vscode.postMessage({ type: 'shell_approval_response', id, approved: false, approve_all: false });
            cleanup();
        };
    }

    const statusEl = document.getElementById('status');
    const spinnerEl = document.getElementById('spinner');
    const chatLog = document.getElementById('chatLog');
    const messageInput = document.getElementById('messageInput');
    const modeSelect = document.getElementById('modeSelect');
    const sendButton = document.getElementById('sendButton');
    const listToolsButton = document.getElementById('listTools');
    const newSessionButton = document.getElementById('newSession');
    const reconnectButton = document.getElementById('reconnect');

    sendButton.addEventListener('click', onSend);
    // Message history for up/down arrow navigation
    const messageHistory = [];
    let historyIndex = -1;
    messageInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            onSend();
        } else if (event.key === 'ArrowUp' && !event.shiftKey) {
            if (messageHistory.length === 0) return;
            if (historyIndex === -1) {
                historyIndex = messageHistory.length - 1;
            } else if (historyIndex > 0) {
                historyIndex--;
            }
            messageInput.value = messageHistory[historyIndex] || '';
            event.preventDefault();
        } else if (event.key === 'ArrowDown' && !event.shiftKey) {
            if (messageHistory.length === 0) return;
            if (historyIndex === -1) return;
            if (historyIndex < messageHistory.length - 1) {
                historyIndex++;
                messageInput.value = messageHistory[historyIndex] || '';
            } else {
                historyIndex = -1;
                messageInput.value = '';
            }
            event.preventDefault();
        } else if (!event.ctrlKey && !event.metaKey && !event.altKey) {
            historyIndex = -1;
        }
    });
    listToolsButton.addEventListener('click', () => vscode.postMessage({ type: 'listTools' }));
    newSessionButton.addEventListener('click', () => vscode.postMessage({ type: 'newSession' }));
    reconnectButton.addEventListener('click', () => vscode.postMessage({ type: 'reconnect' }));

    function setSendEnabled(enabled) {
        sendButton.disabled = !enabled;
        messageInput.disabled = !enabled;
    }

    function onSend() {
        const text = messageInput.value.trim();
        if (!text) {
            return;
        }
        const mode = modeSelect ? modeSelect.value : 'default';
        appendEntry('user', text + (mode === 'plan' ? ' (Plan mode)' : ''));
            const thinkingElements = ensureThinkingElements();
            const reasoningEl = thinkingElements.reasoningEl;
            const contentEl = thinkingElements.contentEl;
            if (reasoningEl) {
                reasoningEl.innerHTML = '';
                if (reasoningEl.dataset && 'raw' in reasoningEl.dataset) {
                    delete reasoningEl.dataset.raw;
                } else {
                    reasoningEl.removeAttribute('data-raw');
                }
            }
            if (contentEl) {
                contentEl.innerHTML = '';
                if (contentEl.dataset && 'raw' in contentEl.dataset) {
                    delete contentEl.dataset.raw;
                } else {
                    contentEl.removeAttribute('data-raw');
                }
            }
        chatLog.scrollTop = chatLog.scrollHeight;
        showSpinner(true);
        setSendEnabled(false);
        vscode.postMessage({ type: 'send', content: text, mode });
        // Store in history, max 10
        messageHistory.push(text);
        if (messageHistory.length > 10) messageHistory.shift();
        historyIndex = -1;
        messageInput.value = '';
    }

    function showSpinner(show) {
        if (spinnerEl) {
            if (show) {
                spinnerEl.style.display = '';
                spinnerEl.innerHTML = `<svg width="18" height="18" viewBox="0 0 50 50"><circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-dasharray="31.4 31.4" transform="rotate(-90 25 25)"></circle></svg> <span class="thinking-label">Thinking…</span>`;
            } else {
                spinnerEl.style.display = 'none';
                spinnerEl.innerHTML = '';
            }
        }
    }

    function ensureThinkingElements() {
        let thinkingDiv = document.getElementById('thinking-entry');
        let created = false;
        if (!thinkingDiv) {
            thinkingDiv = document.createElement('div');
            thinkingDiv.className = 'chat-entry assistant thinking';
            thinkingDiv.id = 'thinking-entry';
            thinkingDiv.innerHTML = `<span class="chat-label">Assistant:</span> <span class="spinner-inline"></span> <span class="thinking-label">Thinking…</span>`;
            thinkingDiv.appendChild(document.createElement('br'));
            const reasoningSpan = document.createElement('span');
            reasoningSpan.id = 'thinking-reasoning';
            thinkingDiv.appendChild(reasoningSpan);
            thinkingDiv.appendChild(document.createElement('br'));
            const streamSpan = document.createElement('span');
            streamSpan.id = 'stream-content';
            thinkingDiv.appendChild(streamSpan);
            chatLog.appendChild(thinkingDiv);
            created = true;
        }
        let reasoningEl = thinkingDiv.querySelector('#thinking-reasoning');
        if (!reasoningEl) {
            reasoningEl = document.createElement('span');
            reasoningEl.id = 'thinking-reasoning';
            const streamEl = thinkingDiv.querySelector('#stream-content');
            const br = document.createElement('br');
            if (streamEl) {
                streamEl.insertAdjacentElement('beforebegin', br);
                streamEl.insertAdjacentElement('beforebegin', reasoningEl);
            } else {
                thinkingDiv.appendChild(br);
                thinkingDiv.appendChild(reasoningEl);
            }
        }
        let contentEl = thinkingDiv.querySelector('#stream-content');
        if (!contentEl) {
            contentEl = document.createElement('span');
            contentEl.id = 'stream-content';
            thinkingDiv.appendChild(contentEl);
        }
        return { thinkingDiv, reasoningEl, contentEl, created };
    }

    function escapeHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function escapeAttribute(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatInline(text) {
        let escaped = escapeHtml(text);
        escaped = escaped.replace(/`([^`]+)`/g, (_, code) => `<code>${code}</code>`);
        escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/__(.+?)__/g, '<strong>$1</strong>');
        escaped = escaped.replace(/\*(.+?)\*/g, '<em>$1</em>');
        escaped = escaped.replace(/_(.+?)_/g, '<em>$1</em>');
        escaped = escaped.replace(/\[([^\]]+)]\(([^)]+)\)/g, (_, label, url) => `<a href="${escapeAttribute(url)}" target="_blank" rel="noreferrer noopener">${label}</a>`);
        return escaped;
    }

    function renderMarkdown(text) {
        const lines = text.replace(/\r/g, '').split('\n');
        const html = [];
        let inCodeBlock = false;
        let codeLines = [];
        let listType;
        let paragraphLines = [];

        const closeList = () => {
            if (listType) {
                html.push(`</${listType}>`);
                listType = undefined;
            }
        };

        const flushParagraph = () => {
            if (paragraphLines.length > 0) {
                const joined = paragraphLines.join('<br>');
                html.push(`<p>${formatInline(joined)}</p>`);
                paragraphLines = [];
            }
        };

        lines.forEach((line) => {
            if (line.trim().startsWith('```')) {
                flushParagraph();
                closeList();
                if (!inCodeBlock) {
                    inCodeBlock = true;
                    codeLines = [];
                } else {
                    html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
                    inCodeBlock = false;
                }
                return;
            }

            if (inCodeBlock) {
                codeLines.push(line);
                return;
            }

            const trimmed = line.trim();

            // Blank line → paragraph break
            if (!trimmed) {
                closeList();
                flushParagraph();
                return;
            }

            if (trimmed === '---') {
                flushParagraph();
                closeList();
                html.push('<hr>');
                return;
            }

            const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
            if (headingMatch) {
                flushParagraph();
                closeList();
                const level = headingMatch[1].length;
                html.push(`<h${level}>${formatInline(headingMatch[2])}</h${level}>`);
                return;
            }

            const unorderedMatch = trimmed.match(/^[-*]\s+(.*)$/);
            if (unorderedMatch) {
                flushParagraph();
                if (listType !== 'ul') {
                    closeList();
                    listType = 'ul';
                    html.push('<ul>');
                }
                html.push(`<li>${formatInline(unorderedMatch[1])}</li>`);
                return;
            }

            const orderedMatch = trimmed.match(/^\d+\.\s+(.*)$/);
            if (orderedMatch) {
                flushParagraph();
                if (listType !== 'ol') {
                    closeList();
                    listType = 'ol';
                    html.push('<ol>');
                }
                html.push(`<li>${formatInline(orderedMatch[1])}</li>`);
                return;
            }

            // Accumulate normal lines into current paragraph; single newlines → <br>
            closeList();
            paragraphLines.push(trimmed);
        });

        if (inCodeBlock) {
            html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
        }
        flushParagraph();
        closeList();
        return html.join('');
    }

    // let systemGroup = null; // Already declared at the top
    let lastSystemGroup = null;
    function appendEntry(kind, text) {
        // Render all messages (including system) inline, no collapsible/group for system
        const entry = document.createElement('div');
        entry.className = `chat-entry ${kind}`;
        if (kind === 'assistant') {
            entry.innerHTML = `<span class=\"chat-label\">${labelForKind(kind)}</span> ${renderMarkdown(text || '')}`;
        } else {
            entry.innerHTML = `<span class=\"chat-label\">${labelForKind(kind)}</span> ${formatInline(text || '').replace(/\n/g, '<br>')}`;
        }
        chatLog.appendChild(entry);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function labelForKind(kind) {
        switch (kind) {
            case 'user':
                return 'You:';
            case 'assistant':
                return 'Assistant:';
            case 'system':
                return '[System]';
            case 'error':
                return '[Error]';
            default:
                return '';
        }
    }


    function setStatus(level, message) {
        statusEl.textContent = message;
        statusEl.className = `status status-${level}`;
        appendEntry(level === 'error' ? 'error' : 'system', message);
    }

    function setControlsEnabled(enabled) {
        [sendButton, listToolsButton, newSessionButton].forEach((button) => {
            button.disabled = !enabled;
        });
        messageInput.disabled = !enabled;
        if (enabled) {
            messageInput.focus();
        }
    }


    window.addEventListener('message', (event) => {
        const message = event.data;
        if (!message || !message.type) {
            return;
        }
        switch (message.type) {
            case 'assistant_thinking': {
                const thinkingElements = ensureThinkingElements();
                const reasoningEl = thinkingElements.reasoningEl;
                if (reasoningEl && typeof message.message === 'string') {
                    const chunk = message.message.replace(/\r/g, '');
                    const raw = (reasoningEl.dataset && reasoningEl.dataset.raw) ? reasoningEl.dataset.raw + chunk : chunk;
                    if (reasoningEl.dataset) {
                        reasoningEl.dataset.raw = raw;
                    } else {
                        reasoningEl.setAttribute('data-raw', raw);
                    }
                    const html = escapeHtml(raw).replace(/\n/g, '<br>');
                    reasoningEl.innerHTML = html;
                    chatLog.scrollTop = chatLog.scrollHeight;
                }
                break;
            }
            case 'assistant_stream': {
                const thinkingElements = ensureThinkingElements();
                const contentEl = thinkingElements.contentEl;
                if (contentEl && typeof message.message === 'string') {
                    const chunk = message.message.replace(/\r/g, '');
                    const raw = (contentEl.dataset && contentEl.dataset.raw) ? contentEl.dataset.raw + chunk : chunk;
                    if (contentEl.dataset) {
                        contentEl.dataset.raw = raw;
                    } else {
                        contentEl.setAttribute('data-raw', raw);
                    }
                    const html = escapeHtml(raw).replace(/\n/g, '<br>');
                    contentEl.innerHTML = html;
                    chatLog.scrollTop = chatLog.scrollHeight;
                }
                break;
            }
            case 'assistant_final': {
                const thinkingDiv = document.getElementById('thinking-entry');
                if (thinkingDiv) thinkingDiv.remove();
                appendEntry('assistant', message.message || '');
                showSpinner(false);
                setSendEnabled(true);
                break;
            }
            case 'assistant': {
                const thinkingDiv = document.getElementById('thinking-entry');
                if (thinkingDiv) thinkingDiv.remove();
                appendEntry('assistant', message.message || '');
                showSpinner(false);
                setSendEnabled(true);
                break;
            }
            case 'system':
                if (typeof message.message === 'string') {
                    console.log('[Codex Chat][SYSTEM]', message.message);
                }
                showSpinner(false);
                // Do NOT re-enable send button here; only after assistant response
                break;
            case 'status':
                setStatus(message.level || 'info', message.message || '');
                break;
            case 'spinner':
                showSpinner(!!message.show);
                break;
            case 'controls':
                setControlsEnabled(!!message.enabled);
                break;
            case 'shell_approval_request':
                showShellApprovalDialog(message.command, message.id, message.reason);
                break;
            default:
                break;
        }
    });
})();
