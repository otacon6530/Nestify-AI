'use strict';

const vscode = require('vscode');
const { ChatPanel } = require('./panels/chatPanel');

function activate(context) {
    context.subscriptions.push(
        vscode.commands.registerCommand('nestify.openChat', () => {
            ChatPanel.createOrShow(context.extensionUri);
        })
    );
}

function deactivate() {
    ChatPanel.disposeAll();
}

module.exports = {
    activate,
    deactivate,
};
