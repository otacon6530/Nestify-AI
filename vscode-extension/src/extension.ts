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
        // Allow optional streaming debug via UI
        const env = { ...process.env };
        if (msg.debugStream) env['NESTIFY_STREAM_DEBUG'] = '1';
        const proc = spawn(pythonPath, ['-m', 'nestify_bridge'], { env });
        panel.webview.postMessage({ type: 'status', value: 'working' });
        let printed = false;
        proc.stdout.on('data', (data) => {
          const lines = data.toString().split(/\r?\n/).filter(Boolean);
          for (const line of lines) {
            try {
              const evt = JSON.parse(line);
              if (evt.type === 'token') {
                panel.webview.postMessage({ type: 'token', value: evt.value });
                printed = true;
              } else if (evt.type === 'final') {
                panel.webview.postMessage({ type: 'final', result: evt.result, printed });
                try { proc.kill(); } catch {}
              } else if (evt.type === 'error') {
                panel.webview.postMessage({ type: 'error', value: JSON.stringify(evt) });
                try { proc.kill(); } catch {}
              }
            } catch {
              // ignore
            }
          }
        });
        proc.stderr.on('data', (data) => {
          panel.webview.postMessage({ type: 'error', value: data.toString() });
          try { proc.kill(); } catch {}
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
    #flags { display: flex; gap: 8px; align-items: center; }
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
  <div id="flags">
    <label><input type="checkbox" id="debugStream" /> Stream debug</label>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    const msgEl = document.getElementById('msg');
    const btn = document.getElementById('send');
    const out = document.getElementById('output');
    const spinner = document.getElementById('spinner');

    const debugStream = document.getElementById('debugStream');
    btn.addEventListener('click', () => {
      const text = msgEl.value.trim();
      if (!text) return;
      btn.disabled = true; spinner.classList.add('working');
      vscode.postMessage({ type: 'send', text });
      vscode.postMessage({ type: 'send', text, debugStream: debugStream.checked });

    window.addEventListener('message', (ev) => {
      const msg = ev.data;
      if (msg.type === 'token') { out.textContent += msg.value; }
      if (msg.type === 'token') { out.textContent += msg.value; }
      if (msg.type === 'final') {
        // If no tokens were printed, append the final text
        if (!msg.printed && msg.result && msg.result.text) {
          out.textContent += msg.result.text;
        }
        out.textContent += '\n';
        btn.disabled = false; spinner.classList.remove('working');
      }
      if (msg.type === 'status') {
        if (msg.value === 'working') { btn.disabled = true; spinner.classList.add('working'); }
        else { btn.disabled = false; spinner.classList.remove('working'); }
      }
    });
  </script>
</body>
</html>`;
}
