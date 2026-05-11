import { marked } from 'marked';

export class ExplainerPanel {
  constructor(container) {
    this._container = container;
  }

  async load(source) {
    let json;
    try {
      const res = await fetch('/api/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source }),
      });
      json = await res.json();
    } catch {
      return;
    }
    if (!json.ok) return;
    this.render(json.data.explanation);
  }

  render(markdown) {
    this._container.innerHTML = marked.parse(markdown);
  }

  clear() {
    this._container.innerHTML = '';
  }
}
