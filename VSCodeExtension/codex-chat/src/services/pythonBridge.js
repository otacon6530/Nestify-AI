'use strict';

const { spawn } = require('child_process');
const readline = require('readline');
const vscode = require('vscode');
const path = require('path');

class PythonBridge {
    constructor() {
        this.process = undefined;
        this.reader = undefined;
        this.messageEmitter = new vscode.EventEmitter();
        this.errorEmitter = new vscode.EventEmitter();
        this.exitEmitter = new vscode.EventEmitter();
        this.disposables = [this.messageEmitter, this.errorEmitter, this.exitEmitter];
    }

    get onMessage() {
        return this.messageEmitter.event;
    }

    get onError() {
        return this.errorEmitter.event;
    }

    get onExit() {
        return this.exitEmitter.event;
    }

    get isRunning() {
        return !!this.process && !this.process.killed;
    }

    start(workspacePath, pythonPath) {
        if (this.isRunning) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            try {
                // Start Nestify bridge instead of Codex core
                const pyEnv = { ...process.env };
                const srcPath = path.join(workspacePath || '', 'src');
                const delim = path.delimiter;
                pyEnv.PYTHONPATH = [srcPath, pyEnv.PYTHONPATH].filter(Boolean).join(delim);

                const child = spawn(pythonPath || 'python', ['-u', '-m', 'nestify_bridge'], {
                    cwd: workspacePath,
                    env: pyEnv,
                    stdio: ['pipe', 'pipe', 'pipe'],
                });
                this.process = child;

                child.once('error', (err) => {
                    this.errorEmitter.fire(`Python process error: ${err.message}`);
                    reject(err);
                });

                child.once('spawn', () => {
                    this.setupReaders(child);
                    resolve();
                });

                if (child.stderr) {
                    child.stderr.on('data', (data) => {
                        const text = data.toString().trim();
                        if (text.length > 0) {
                            this.errorEmitter.fire(text);
                        }
                    });
                }

                child.on('exit', (code, signal) => {
                    this.exitEmitter.fire({ code, signal });
                    this.disposeReaders();
                    this.process = undefined;
                });
            } catch (error) {
                reject(error);
            }
        });
    }

    setupReaders(child) {
        this.reader = readline.createInterface({
            input: child.stdout,
            crlfDelay: Infinity,
        });

        this.reader.on('line', (line) => this.handleLine(line));
    }

    handleLine(line) {
        const trimmed = line.trim();
        if (!trimmed) {
            return;
        }
        console.log('[Codex Chat] Backend -> Extension:', trimmed);
        try {
            const payload = JSON.parse(trimmed);
            // Translate Nestify bridge protocol into aggregated stream events
            if (payload && payload.type === 'thinking') {
                this.messageEmitter.fire({ type: 'assistant_thinking', content: payload.value || '' });
            } else if (payload && payload.type === 'token') {
                this.messageEmitter.fire({ type: 'assistant_stream', content: payload.value || '' });
            } else if (payload && payload.type === 'final') {
                const text = (payload.result && payload.result.text) || '';
                this.messageEmitter.fire({ type: 'assistant_final', content: text });
            } else if (payload && payload.type === 'error') {
                const msg = payload.message || JSON.stringify(payload);
                this.messageEmitter.fire({ type: 'error', content: msg });
            } else {
                // Pass through unknown messages
                this.messageEmitter.fire(payload);
            }
        } catch (err) {
            this.errorEmitter.fire(`Failed to parse JSON line: ${(err && err.message) || err}\n${trimmed}`);
        }
    }

    send(payload) {
        if (!this.process || !this.process.stdin || this.process.stdin.destroyed) {
            return Promise.reject(new Error('Python process is not running.'));
        }

        return new Promise((resolve, reject) => {
            try {
                // Translate Codex message format to Nestify bridge exec
                let out = payload;
                if (payload && payload.type === 'message') {
                    out = { type: 'exec', text: payload.content || '' };
                }
                this.process.stdin.write(`${JSON.stringify(out)}\n`, (err) => {
                    if (err) {
                        reject(err);
                    } else {
                        resolve();
                    }
                });
            } catch (error) {
                reject(error);
            }
        });
    }

    async stop() {
        if (!this.process) {
            return;
        }
        try {
            await this.send({ type: 'shutdown' });
        } catch (err) {
            // Ignore errors on shutdown attempt
        }
        this.process.kill();
        this.disposeReaders();
        this.process = undefined;
    }

    disposeReaders() {
        if (this.reader) {
            this.reader.removeAllListeners();
            this.reader.close();
            this.reader = undefined;
        }
    }

    dispose() {
        this.stop().catch(() => undefined);
        this.disposables.forEach((d) => d.dispose());
    }
}

module.exports = {
    PythonBridge,
};
