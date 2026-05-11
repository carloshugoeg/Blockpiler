import { io } from 'socket.io-client';

export class Debugger {
  constructor(monacoEditor, blocklyWorkspace, socketURL) {
    this._editor       = monacoEditor;
    this._workspace    = blocklyWorkspace;
    this._socketURL    = socketURL;
    this._socket       = null;
    this._decorations  = [];
    this._varPanel     = null;
    this._stackPanel   = null;
  }

  // ── Public API ──────────────────────────────────────────────────────

  start(source) {
    this._connect();
    this._socket.emit('debug:start', { source });
  }

  step() {
    if (!this._socket) return;
    this._socket.emit('debug:step');
  }

  continue(breakpoints) {
    if (!this._socket) return;
    this._socket.emit('debug:continue', {
      breakpoints: [...(breakpoints ?? [])],
    });
  }

  stop() {
    if (!this._socket) return;
    this._socket.emit('debug:stop');
    this._socket.disconnect();
    this._socket = null;
    this._clearHighlight();
  }

  // Creates Step / Continue / Stop buttons and variable + call-stack panels
  // inside `container`. Must be called before start().
  mountUI(container) {
    container.innerHTML = '';

    const controls = document.createElement('div');
    controls.className = 'dbg-controls';

    const btnStep = document.createElement('button');
    btnStep.textContent = 'Step';
    btnStep.onclick = () => this.step();

    const btnContinue = document.createElement('button');
    btnContinue.textContent = 'Continue';
    btnContinue.onclick = () => this.continue(new Set());

    const btnStop = document.createElement('button');
    btnStop.textContent = 'Stop';
    btnStop.onclick = () => this.stop();

    controls.append(btnStep, btnContinue, btnStop);

    const varPanel = document.createElement('div');
    varPanel.className = 'dbg-variables';

    const stackPanel = document.createElement('div');
    stackPanel.className = 'dbg-callstack';

    container.append(controls, varPanel, stackPanel);

    this._varPanel   = varPanel;
    this._stackPanel = stackPanel;
  }

  // ── Private ─────────────────────────────────────────────────────────

  _connect() {
    if (this._socket) return;
    this._socket = io(this._socketURL);
    this._socket.on('debug:state', (state) => this._onState(state));
    this._socket.on('debug:error', (err)   => this._onError(err));
  }

  _onState(state) {
    if (state == null) return;
    this._highlightLine(state.line ?? 0);
    this._updateVariablesPanel(state.variables   ?? {});
    this._updateCallStack(state.call_stack ?? []);
  }

  // eslint-disable-next-line no-unused-vars
  _onError(_err) {
    // Surface to UI when a debug-error panel is mounted
  }

  _highlightLine(line) {
    // Monaco: replace previous decoration with a whole-line highlight
    if (this._editor && typeof this._editor.deltaDecorations === 'function') {
      this._decorations = this._editor.deltaDecorations(this._decorations, [
        {
          range: {
            startLineNumber: line,
            startColumn: 1,
            endLineNumber: line,
            endColumn: 9999,
          },
          options: { isWholeLine: true, className: 'dbg-current-line' },
        },
      ]);
    }

    // Blockly: highlight the block whose srcLine matches
    if (this._workspace && typeof this._workspace.getAllBlocks === 'function') {
      const blocks = this._workspace.getAllBlocks(false);
      let targetId = null;
      for (const block of blocks) {
        let srcLine = null;
        try {
          const data = block.data ? JSON.parse(block.data) : null;
          if (data) srcLine = data.srcLine;
        } catch {
          // malformed block.data — skip
        }
        if (srcLine === line) {
          targetId = block.id;
          break;
        }
      }
      if (typeof this._workspace.highlightBlock === 'function') {
        this._workspace.highlightBlock(targetId);
      }
    }
  }

  _clearHighlight() {
    if (this._editor && typeof this._editor.deltaDecorations === 'function') {
      this._decorations = this._editor.deltaDecorations(this._decorations, []);
    }
    if (this._workspace && typeof this._workspace.highlightBlock === 'function') {
      this._workspace.highlightBlock(null);
    }
  }

  _updateVariablesPanel(variables) {
    if (!this._varPanel) return;
    this._varPanel.innerHTML = '';
    for (const [name, value] of Object.entries(variables)) {
      const type = value === null ? 'null' : typeof value;
      const row  = document.createElement('div');
      row.className = 'dbg-var-row';
      row.innerHTML =
        `<span class="dbg-var-name">${_esc(name)}</span>` +
        `<span class="dbg-var-type">${_esc(type)}</span>` +
        `<span class="dbg-var-value">${_esc(String(value))}</span>`;
      this._varPanel.appendChild(row);
    }
  }

  _updateCallStack(callStack) {
    if (!this._stackPanel) return;
    this._stackPanel.innerHTML = '';
    for (const frame of callStack) {
      const item = document.createElement('div');
      item.className = 'dbg-stack-frame';
      item.textContent = frame;
      this._stackPanel.appendChild(item);
    }
  }
}

function _esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
