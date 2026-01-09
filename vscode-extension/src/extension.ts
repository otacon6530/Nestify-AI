import * as vscode from 'vscode';
import { spawn } from 'child_process';

export function activate(context: vscode.ExtensionContext) {
  const disposable = vscode.commands.registerCommand('nestify.openChat', () => {
    const panel = vscode.window.createWebviewPanel(
      'nestifyChat',
      'Nestify Chat',
      vscode.ViewColumn.Active,
      { enableScripts: true }
    );

    panel.webview.html = getHtml();

    panel.webview.onDidReceiveMessage(async (msg) => {
      if (msg.type === 'send') {
        const pythonPath = vscode.workspace.getConfiguration().get<string>('nestify.pythonPath', 'python');
        const proc = spawn(pythonPath, ['-m', 'nestify_bridge']);
        panel.webview.postMessage({ type: 'status', value: 'working' });
        proc.stdout.on('data', (data) => {
          const lines = data.toString().split(/\r?\n/).filter(Boolean);
          for (const line of lines) {
            try {
              const evt = JSON.parse(line);
              if (evt.type === 'token') {
                panel.webview.postMessage({ type: 'token', value: evt.value });
              } else if (evt.type === 'final') {
                panel.webview.postMessage({ type: 'final', result: evt.result });
              } else if (evt.type === 'error') {
                panel.webview.postMessage({ type: 'error', value: JSON.stringify(evt) });
              }
            } catch {
              // ignore
            }
          }
        });
        proc.stderr.on('data', (data) => {
          panel.webview.postMessage({ type: 'error', value: data.toString() });
        });
        proc.on('exit', () => {
          panel.webview.postMessage({ type: 'status', value: 'idle' });
        });
        proc.stdin.write(JSON.stringify({ type: 'exec', text: msg.text }) + '\n');
      }
    });
  });

  context.subscriptions.push(disposable);
}

export function deactivate() {}

function getHtml(): string {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <style>
    body { font-family: sans-serif; padding: 10px; }
    #controls { display: flex; gap: 8px; }
    #output { white-space: pre-wrap; border: 1px solid #ccc; padding: 8px; min-height: 120px; }
    #spinner { display: none; }
    #spinner.working { display: inline-block; }
  </style>
</head>
<body>
  <div id="controls">
    <select id="mode">
      <option value="default" selected>Default</option>
      <option value="plan">Plan</option>
    </select>
    <input id="msg" type="text" placeholder="Type message..." style="flex:1" />
    <button id="send">Send</button>
    <span id="spinner">⏳</span>
  </div>
  <div id="output"></div>
  <script>
    const vscode = acquireVsCodeApi();
    const msgEl = document.getElementById('msg');
    const btn = document.getElementById('send');
    const out = document.getElementById('output');
    const spinner = document.getElementById('spinner');

    btn.addEventListener('click', () => {
      const text = msgEl.value.trim();
      if (!text) return;
      btn.disabled = true; spinner.classList.add('working');
      vscode.postMessage({ type: 'send', text });
    });

    window.addEventListener('message', (ev) => {
      const msg = ev.data;
      if (msg.type === 'token') { out.textContent += msg.value; }
      if (msg.type === 'final') { btn.disabled = false; spinner.classList.remove('working'); }
      if (msg.type === 'error') { out.textContent += '\n[error] ' + msg.value; btn.disabled = false; spinner.classList.remove('working'); }
      if (msg.type === 'status') {
        if (msg.value === 'working') { btn.disabled = true; spinner.classList.add('working'); }
        else { btn.disabled = false; spinner.classList.remove('working'); }
      }
    });
  </script>
</body>
</html>`;
}
