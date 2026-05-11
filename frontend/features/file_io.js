const AUTO_SAVE_KEY = 'compileflow_autosave';
const AUTO_SAVE_MAX = 5;

function _download(filename, content, mimeType = 'text/plain') {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

export function saveAsC(source) {
    _download('program.c', source, 'text/plain');
}

export function saveAsAsm(assembly) {
    _download('program.s', assembly, 'text/plain');
}

export function saveAsCfproj(state) {
    _download('project.cfproj', JSON.stringify(state, null, 2), 'application/json');
}

export function saveAsScratch(workspace) {
    _download('workspace.scratch', JSON.stringify(workspace, null, 2), 'application/json');
}

export function saveAsPng(canvas) {
    const url = canvas.toDataURL('image/png');
    const a = document.createElement('a');
    a.href = url;
    a.download = 'diagram.png';
    a.click();
}

export async function loadFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    const typeMap = { c: 'c', s: 'asm', cfproj: 'cfproj', scratch: 'scratch' };
    const fileType = typeMap[ext];

    const text = await file.text();

    const res = await fetch('/api/validate-file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, content: text, file_type: fileType || 'c' }),
    });
    const json = await res.json();
    if (!json.ok) throw new Error(json.errors?.[0]?.message ?? 'Archivo inválido');

    let content = json.content;
    if (fileType === 'cfproj' || fileType === 'scratch') {
        try { content = JSON.parse(content); } catch { /* keep as string */ }
    }
    return { type: fileType ?? ext, content };
}

export function autoSave(state) {
    let versions;
    try {
        versions = JSON.parse(localStorage.getItem(AUTO_SAVE_KEY) ?? '[]');
    } catch {
        versions = [];
    }
    versions.unshift({ ts: Date.now(), state });
    if (versions.length > AUTO_SAVE_MAX) versions.length = AUTO_SAVE_MAX;
    localStorage.setItem(AUTO_SAVE_KEY, JSON.stringify(versions));
}

export function loadAutoSave() {
    try {
        const versions = JSON.parse(localStorage.getItem(AUTO_SAVE_KEY) ?? '[]');
        return versions.length > 0 ? versions[0].state : null;
    } catch {
        return null;
    }
}
