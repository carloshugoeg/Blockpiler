import * as Blockly from 'blockly';

export class SyncManager {
  constructor(monacoEditor, blocklyWorkspace, apiBase = '') {
    this._editor = monacoEditor;
    this._workspace = blocklyWorkspace;
    this._apiBase = apiBase;
    this._guard = false;
    this._debounceTimer = null;
    this._ideDisposable = null;
    this._blocksListener = null;
  }

  async flushIdeToBlocks() {
    clearTimeout(this._debounceTimer);
    this._debounceTimer = null;
    return this._syncIdeToBlocks();
  }

  async flushBlocksToIde() {
    return this._syncBlocksToIde();
  }

  async _syncIdeToBlocks() {
    const source = this._editor.getValue();
    let json;
    try {
      const res = await fetch(`${this._apiBase}/api/convert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction: 'c_to_blocks', source }),
      });
      json = await res.json();
    } catch {
      return;
    }
    if (!json.ok) return;
    this._guard = true;
    try {
      Blockly.serialization.workspaces.load(json.data.workspace, this._workspace);
    } finally {
      this._guard = false;
    }
  }

  async _syncBlocksToIde() {
    const workspaceState = Blockly.serialization.workspaces.save(this._workspace);
    let json;
    try {
      const res = await fetch(`${this._apiBase}/api/convert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction: 'blocks_to_c', workspace: workspaceState }),
      });
      json = await res.json();
    } catch {
      return;
    }
    if (!json.ok) return;
    this._guard = true;
    try {
      this._editor.setValue(json.data.source);
    } finally {
      this._guard = false;
    }
  }

  _onIdeChange(handler) {
    return this._editor.onDidChangeModelContent(handler);
  }

  _onBlocksChange(handler) {
    this._workspace.addChangeListener(handler);
  }

  enableSync() {
    this._ideDisposable = this._editor.onDidChangeModelContent(() => {
      if (this._guard) return;
      clearTimeout(this._debounceTimer);
      this._debounceTimer = setTimeout(() => {
        this._debounceTimer = null;
        this._syncIdeToBlocks();
      }, 600);
    });

    this._blocksListener = (event) => {
      if (this._guard) return;
      if (event && event.isUiEvent) return;
      this._syncBlocksToIde();
    };
    this._workspace.addChangeListener(this._blocksListener);
  }

  disableSync() {
    if (this._ideDisposable) {
      this._ideDisposable.dispose();
      this._ideDisposable = null;
    }
    if (this._blocksListener) {
      this._workspace.removeChangeListener(this._blocksListener);
      this._blocksListener = null;
    }
    clearTimeout(this._debounceTimer);
    this._debounceTimer = null;
  }
}
