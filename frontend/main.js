import * as Blockly from 'blockly';
import { setupMonaco, getEditorValue, setEditorValue, getEditor } from './ide/monaco_setup.js';
import { setupBlockly, getWorkspace, getWorkspaceJSON, loadWorkspaceJSON } from './blocks/blockly_setup.js';
import { AsmPanel } from './features/asm_panel.js';
import { ASTViewer } from './features/ast_viewer.js';
import { Debugger } from './features/debugger.js';
import { ExplainerPanel } from './features/explainer.js';
import { Gallery } from './features/gallery.js';
import { ShareManager } from './features/share.js';
import {
  saveAsC, saveAsAsm, saveAsCfproj,
  loadFile, autoSave, loadAutoSave,
} from './features/file_io.js';
import { SyncManager } from './features/sync.js';

// ── Build DOM shell ────────────────────────────────────────────────────────
document.getElementById('app').innerHTML = `
<div id="shell">
  <header id="toolbar" class="app-header">
    <div class="brand-area">
      <div class="toolbar-brand">
        <span class="brand-mark" aria-hidden="true">CF</span>
        <span>CompileFlow</span>
      </div>
      <nav class="breadcrumbs" aria-label="Ruta del proyecto">
        <span>Proyectos</span>
        <span aria-hidden="true">/</span>
        <strong>Factorial</strong>
      </nav>
    </div>

    <div class="toolbar-actions">
      <div class="btn-group primary-actions">
        <button id="btn-compile" class="btn btn-primary">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7-11-7Z"/></svg>
          <span>Compilar</span>
        </button>
        <button id="btn-run" class="btn">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4v16l14-8L5 4Z"/></svg>
          <span>Ejecutar</span>
        </button>
        <button id="btn-ast" class="btn active" data-panel-target="ast-container">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M11 4h2v4h4v2h-4v4h4v2h-4v4h-2v-4H7v-2h4v-4H7V8h4V4Z"/></svg>
          <span>AST</span>
        </button>
        <button id="btn-asm" class="btn" data-panel-target="asm-container">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v3H4V5Zm0 5h16v3H4v-3Zm0 5h10v3H4v-3Z"/></svg>
          <span>Ensamblador</span>
        </button>
        <button id="btn-debug" class="btn" data-panel-target="debug-container">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3h8v3h3v3h2v2h-2v2h2v2h-2v3h-3v3H8v-3H5v-3H3v-2h2v-2H3V9h2V6h3V3Zm2 5v8h4V8h-4Z"/></svg>
          <span>Depurar</span>
        </button>
        <button id="btn-explain" class="btn" data-panel-target="explain-container">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v12H8l-3 4V4Zm4 4v2h6V8H9Zm0 4v2h9v-2H9Z"/></svg>
          <span>Explicar</span>
        </button>
      </div>

      <div class="btn-group file-actions">
        <div class="dropdown">
          <button id="btn-gallery" class="btn btn-quiet">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h7v7H4V5Zm9 0h7v7h-7V5ZM4 14h7v5H4v-5Zm9 0h7v5h-7v-5Z"/></svg>
            <span>Galería</span>
            <span class="chevron" aria-hidden="true">▾</span>
          </button>
          <div class="dropdown-menu" id="gallery-menu"></div>
        </div>
        <button id="btn-share" class="btn btn-quiet">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 16.1c-.8 0-1.5.3-2 .8L8.9 12.8c.1-.3.1-.5.1-.8s0-.5-.1-.8L16 7.1c.5.5 1.2.8 2 .8a3 3 0 1 0-3-3c0 .3 0 .5.1.8L8 9.8A3 3 0 1 0 8 14.2l7.1 4.2c-.1.2-.1.5-.1.7a3 3 0 1 0 3-3Z"/></svg>
          <span>Compartir</span>
        </button>
        <button id="btn-open" class="btn btn-quiet">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h6l2 2h8v10H4V6Zm2 4v6h12v-6H6Z"/></svg>
          <span>Abrir</span>
        </button>
        <div class="dropdown">
          <button id="btn-save" class="btn btn-quiet">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h12l2 2v14H5V4Zm3 2v5h8V6H8Zm0 8v4h8v-4H8Z"/></svg>
            <span>Guardar</span>
            <span class="chevron" aria-hidden="true">▾</span>
          </button>
          <div class="dropdown-menu" id="save-menu">
            <button class="dropdown-item" data-save="c">Guardar como .c</button>
            <button class="dropdown-item" data-save="asm">Guardar como .s</button>
            <button class="dropdown-item" data-save="cfproj">Guardar proyecto</button>
          </div>
        </div>
      </div>
    </div>
  </header>

  <div id="workspace" class="app-workspace">

    <section id="code-view" class="workspace-view active">
      <div id="left-panel" class="surface-panel code-panel">
        <div class="panel-tabs" id="left-tabs">
          <button class="tab-btn" data-target="editor-container">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 7 3 12l5 5 1.4-1.4L5.8 12l3.6-3.6L8 7Zm8 0-1.4 1.4 3.6 3.6-3.6 3.6L16 17l5-5-5-5Z"/></svg>
            <span>Código</span>
          </button>
          <button class="tab-btn active" data-target="blocks-container">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h7v6H4V5Zm9 0h7v6h-7V5ZM4 13h7v6H4v-6Zm9 0h7v6h-7v-6Z"/></svg>
            <span>Blockly</span>
          </button>
          <button id="btn-toggle-palette" class="tab-action">Paleta</button>
          <button id="btn-clear-blocks" class="tab-action">Limpiar</button>
        </div>
        <div class="panel-body code-body">
          <aside id="blocks-palette-panel" class="blocks-palette-panel">
            <div class="palette-title">Paleta de bloques</div>
            <div class="palette-chip-row">
              <span class="palette-chip variables">Variables</span>
              <span class="palette-chip control">Control</span>
              <span class="palette-chip functions">Funciones</span>
              <span class="palette-chip io">I/O</span>
              <span class="palette-chip operators">Operadores</span>
              <span class="palette-chip arrays">Arrays</span>
              <span class="palette-chip types">Tipos</span>
            </div>
          </aside>
          <div id="editor-container" class="panel-content hidden"></div>
          <div id="blocks-container" class="panel-content"></div>
        </div>
      </div>

      <div id="panel-divider"></div>

      <div id="right-panel" class="surface-panel info-panel">
        <div class="panel-body info-body">
          <div id="ast-container" class="panel-content"></div>
          <div id="asm-container" class="panel-content hidden"></div>
          <div id="debug-container" class="panel-content hidden"></div>
          <div id="explain-container" class="panel-content hidden"></div>
        </div>
      </div>
    </section>



  </div>

  <div id="console">
    <div class="console-header">
      <span>Salida</span>
      <button id="btn-clear-console" class="btn-sm">Limpiar</button>
    </div>
    <pre id="console-output"></pre>
  </div>
</div>
<input type="file" id="file-input" accept=".c,.s,.cfproj,.scratch" style="display:none">
`;

// ── Initialize editors ─────────────────────────────────────────────────────
setupMonaco(document.getElementById('editor-container'));
setupBlockly(document.getElementById('blocks-container'));

const editor    = getEditor();
const workspace = getWorkspace();

// ── Create module instances ────────────────────────────────────────────────
const asmPanel  = new AsmPanel(document.getElementById('asm-container'), editor);
const astViewer = new ASTViewer(document.getElementById('ast-container'));
const debugInst = new Debugger(editor, workspace, 'http://localhost:5000');
const explainer = new ExplainerPanel(document.getElementById('explain-container'));
const gallery   = new Gallery(editor);
const shareMan  = new ShareManager();
const syncMan   = new SyncManager(editor, workspace);

debugInst.mountUI(document.getElementById('debug-container'));

let lastAssembly = '';
let autoSaveTimer = null;

// ── Console helpers ────────────────────────────────────────────────────────
function printConsole(text, isError = false) {
  const pre = document.getElementById('console-output');
  pre.textContent += text + '\n';
  if (isError) pre.classList.add('has-errors');
  pre.scrollTop = pre.scrollHeight;
}

function clearConsole() {
  const pre = document.getElementById('console-output');
  pre.textContent = '';
  pre.classList.remove('has-errors');
}

// ── Tab switching ──────────────────────────────────────────────────────────
function activateTab(tabsId, targetId) {
  const tabsEl    = document.getElementById(tabsId);
  if (!tabsEl) return;
  const panelBody = tabsEl.nextElementSibling;
  tabsEl.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.target === targetId);
  });
  panelBody.querySelectorAll('.panel-content').forEach(el => {
    el.classList.toggle('hidden', el.id !== targetId);
  });
}

function activateRightPanel(targetId) {
  document.querySelectorAll('[data-panel-target]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.panelTarget === targetId);
  });
  document.querySelectorAll('#right-panel .panel-content').forEach(el => {
    el.classList.toggle('hidden', el.id !== targetId);
  });
}

function refreshActiveSurface() {
  const activeLeftTab = document.querySelector('#left-tabs .tab-btn.active');
  if (activeLeftTab?.dataset.target === 'editor-container') {
    editor?.layout();
  } else if (activeLeftTab?.dataset.target === 'blocks-container') {
    Blockly.svgResize(workspace);
  }
}

function activateMainView() {
  const codeView = document.getElementById('code-view');
  codeView?.classList.add('active');
  refreshActiveSurface();
}

function parseLoadedJSON(content) {
  return typeof content === 'string' ? JSON.parse(content) : content;
}

function clearBlocksWorkspace() {
  const ws = getWorkspace();
  if (!ws) return;
  ws.clear();
  if (typeof ws.clearUndo === 'function') ws.clearUndo();
  Blockly.svgResize(ws);
}

function cleanIdeAndBlocks() {
  setEditorValue('');
  clearBlocksWorkspace();
}

async function loadSourceAfterClean(source) {
  syncMan.disableSync();
  try {
    cleanIdeAndBlocks();
    setEditorValue(source ?? '');
  } finally {
    syncMan.enableSync();
  }
  await syncMan._syncIdeToBlocks();
}

async function loadWorkspaceAfterClean(workspaceJson) {
  syncMan.disableSync();
  try {
    cleanIdeAndBlocks();
    loadWorkspaceJSON(workspaceJson);
  } finally {
    syncMan.enableSync();
  }
  await syncMan._syncBlocksToIde();
}

async function loadProjectAfterClean(project) {
  syncMan.disableSync();
  try {
    cleanIdeAndBlocks();
    if (project?.source) setEditorValue(project.source);
    if (project?.workspace) loadWorkspaceJSON(project.workspace);
  } finally {
    syncMan.enableSync();
  }

  if (project?.source && !project?.workspace) {
    await syncMan._syncIdeToBlocks();
  } else if (project?.workspace && !project?.source) {
    await syncMan._syncBlocksToIde();
  }
}

document.getElementById('left-tabs').addEventListener('click', e => {
  const btn = e.target.closest('.tab-btn');
  if (!btn) return;
  activateTab('left-tabs', btn.dataset.target);
  const clearBtn = document.getElementById('btn-clear-blocks');
  const paletteBtn = document.getElementById('btn-toggle-palette');
  if (btn.dataset.target === 'editor-container') {
    editor?.layout();
    clearBtn.classList.add('hidden');
    paletteBtn.classList.add('hidden');
  } else if (btn.dataset.target === 'blocks-container') {
    Blockly.svgResize(workspace);
    clearBtn.classList.remove('hidden');
    paletteBtn.classList.remove('hidden');
  }
});

document.getElementById('btn-toggle-palette').onclick = () => {
  document.getElementById('left-panel').classList.toggle('palette-collapsed');
  Blockly.svgResize(workspace);
};

document.getElementById('btn-clear-blocks').onclick = () => {
  clearBlocksWorkspace();
};

// ── Compile — loads AST + assembly + explanation ───────────────────────────
async function compile() {
  const source = getEditorValue();
  clearConsole();
  printConsole('Compilando…');
  try {
    const res  = await fetch('/api/compile', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ source, optimization_level: 1, include_explanation: true }),
    });
    const data = await res.json();
    clearConsole();

    if (data.ok) {
      lastAssembly = data.data.assembly ?? '';

      // Assembly
      asmPanel.render(lastAssembly, data.data.line_map ?? {});

      // AST
      astViewer.render(data.data.ast ?? null);

      // Explanation
      if (data.data.explanation) {
        explainer.render(data.data.explanation);
      }

      const warns = (data.data.warnings ?? [])
        .map(w => `[aviso] línea ${w.line}: ${w.message}`)
        .join('\n');
      if (warns) printConsole(warns);
      printConsole('Compilación exitosa. Paneles AST, Ensamblador y Explicación actualizados.');
      activateRightPanel('asm-container');
    } else {
      const errs = (data.errors ?? [])
        .map(e => `[${e.severity}] línea ${e.line}: ${e.message}`)
        .join('\n');
      printConsole(errs || 'Error de compilación.', true);
    }
  } catch (err) {
    clearConsole();
    printConsole(`Error de red: ${err.message}`, true);
  }
}

// ── Run — uses interpreter for real output ─────────────────────────────────
async function run() {
  const source = getEditorValue();
  clearConsole();
  printConsole('Ejecutando…');
  try {
    const res  = await fetch('/api/run', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ source }),
    });
    const data = await res.json();
    clearConsole();

    if (data.ok) {
      const out = data.data.stdout || '(sin salida)';
      printConsole(out);
      if (data.data.returncode !== 0) {
        printConsole(`[código de salida: ${data.data.returncode}]`, true);
      }
    } else {
      const errs = (data.errors ?? [])
        .map(e => `[${e.severity}] línea ${e.line}: ${e.message}`)
        .join('\n');
      printConsole(errs || 'Error al ejecutar.', true);
    }
  } catch (err) {
    clearConsole();
    printConsole(`Error de red: ${err.message}`, true);
  }
}

// ── Toolbar buttons ────────────────────────────────────────────────────────
document.getElementById('btn-compile').onclick = compile;
document.getElementById('btn-run').onclick     = run;

document.getElementById('btn-ast').onclick = () => {
  activateRightPanel('ast-container');
};

document.getElementById('btn-asm').onclick = () => {
  activateRightPanel('asm-container');
};

document.getElementById('btn-debug').onclick = () => {
  activateMainView();
  activateRightPanel('debug-container');
  debugInst.start(getEditorValue());
};

document.getElementById('btn-explain').onclick = () => {
  activateMainView();
  activateRightPanel('explain-container');
  explainer.load(getEditorValue());
};

document.getElementById('btn-share').onclick = () => {
  shareMan.share({ source: getEditorValue(), workspace: getWorkspaceJSON() });
};

document.getElementById('btn-clear-console').onclick = clearConsole;

// ── Gallery dropdown ───────────────────────────────────────────────────────
const galleryMenu = document.getElementById('gallery-menu');
gallery.getExamples().forEach(ex => {
  const item       = document.createElement('button');
  item.className   = 'dropdown-item';
  item.textContent = ex.name;
  item.onclick     = async () => {
    await loadSourceAfterClean(ex.source);
    galleryMenu.classList.remove('open');
  };
  galleryMenu.appendChild(item);
});

document.getElementById('btn-gallery').onclick = e => {
  e.stopPropagation();
  galleryMenu.classList.toggle('open');
  document.getElementById('save-menu').classList.remove('open');
};

// ── Save dropdown ──────────────────────────────────────────────────────────
const saveMenu = document.getElementById('save-menu');
document.getElementById('btn-save').onclick = e => {
  e.stopPropagation();
  saveMenu.classList.toggle('open');
  galleryMenu.classList.remove('open');
};

saveMenu.addEventListener('click', e => {
  const btn = e.target.closest('[data-save]');
  if (!btn) return;
  const type = btn.dataset.save;
  if (type === 'c')      saveAsC(getEditorValue());
  if (type === 'asm')    saveAsAsm(lastAssembly);
  if (type === 'cfproj') saveAsCfproj({ source: getEditorValue(), workspace: getWorkspaceJSON() });
  saveMenu.classList.remove('open');
});

document.addEventListener('click', () => {
  galleryMenu.classList.remove('open');
  saveMenu.classList.remove('open');
});

// ── File open ──────────────────────────────────────────────────────────────
const fileInput = document.getElementById('file-input');
document.getElementById('btn-open').onclick = () => fileInput.click();

fileInput.onchange = async e => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const result = await loadFile(file);
    if (result.type === 'c') {
      await loadSourceAfterClean(result.content);
    } else if (result.type === 'scratch') {
      await loadWorkspaceAfterClean(parseLoadedJSON(result.content));
    } else if (result.type === 'cfproj') {
      await loadProjectAfterClean(parseLoadedJSON(result.content));
    }
  } catch (err) {
    printConsole(`Error al abrir archivo: ${err.message}`, true);
  }
  fileInput.value = '';
};

// ── Auto-save ──────────────────────────────────────────────────────────────
editor.onDidChangeModelContent(() => {
  clearTimeout(autoSaveTimer);
  autoSaveTimer = setTimeout(() => {
    autoSave({ source: getEditorValue(), workspace: getWorkspaceJSON() });
  }, 1000);
});

// ── Sync ───────────────────────────────────────────────────────────────────
syncMan.enableSync();

// ── Initial state ──────────────────────────────────────────────────────────
const sharedState = shareMan.loadFromURL();
if (sharedState?.source || sharedState?.workspace) {
  void loadProjectAfterClean(sharedState);
} else {
  const saved = loadAutoSave();
  if (saved?.source || saved?.workspace) void loadProjectAfterClean(saved);
}


