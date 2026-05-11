import * as d3 from 'd3';

export class ASTViewer {
  constructor(container) {
    this._container     = container;
    this._clickCallback = null;
    this._svg           = null;
  }

  render(astData) {
    this.clear();
    if (!astData) return;

    const width  = this._container.clientWidth  || 800;
    const height = this._container.clientHeight || 600;

    const root = this._buildD3Tree(astData);
    d3.tree().size([width, height - 80])(root);

    const svg = d3.select(this._container)
      .append('svg')
      .attr('width', width)
      .attr('height', height);

    this._svg = svg;

    const g = svg.append('g').attr('transform', 'translate(40,40)');

    svg.call(
      d3.zoom()
        .scaleExtent([0.1, 3])
        .on('zoom', (e) => g.attr('transform', e.transform)),
    );

    this._renderLinks(g, root.links());
    this._renderNodes(g, root.descendants());
  }

  highlight(nodeId) {
    if (!this._svg) return;
    this._svg.selectAll('.node').classed('highlighted', false);
    this._svg.selectAll(`.node[data-id="${nodeId}"]`).classed('highlighted', true);
  }

  clear() {
    d3.select(this._container).selectAll('*').remove();
    this._svg = null;
  }

  _buildD3Tree(astData) {
    const root = d3.hierarchy(astData, (node) => {
      if (!node || typeof node !== 'object') return null;
      const children = [];
      for (const [key, val] of Object.entries(node)) {
        if (key === 'pos' || key === 'inferred_type') continue;
        if (val && typeof val === 'object' && !Array.isArray(val) && 'type' in val) {
          children.push(val);
        } else if (Array.isArray(val)) {
          for (const item of val) {
            if (item && typeof item === 'object' && 'type' in item) {
              children.push(item);
            }
          }
        }
      }
      return children.length > 0 ? children : null;
    });
    let counter = 0;
    root.each((d) => { d.id = `n${counter++}`; });
    return root;
  }

  _renderLinks(g, links) {
    const linkPath = d3.linkVertical().x((d) => d.x).y((d) => d.y);
    g.selectAll('.link')
      .data(links)
      .join('path')
      .classed('link', true)
      .attr('fill', 'none')
      .attr('stroke', '#aaa')
      .attr('d', linkPath);
  }

  _renderNodes(g, nodes) {
    const nodeG = g.selectAll('.node')
      .data(nodes)
      .join('g')
      .classed('node', true)
      .attr('data-id', (d) => d.id)
      .attr('transform', (d) => `translate(${d.x},${d.y})`)
      .on('click', (event, d) => this._handleNodeClick(d));

    nodeG.append('circle')
      .attr('r', 18)
      .attr('fill', '#4a9eff')
      .attr('stroke', '#2176cc');

    // Node type label (e.g. "BinaryOp", "IfStmt")
    nodeG.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '-22px')
      .attr('font-size', '11px')
      .text((d) => d.data.type || '');

    // Inferred type sublabel (e.g. "int")
    nodeG.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '-8px')
      .attr('font-size', '9px')
      .attr('fill', '#888')
      .classed('inferred-type', true)
      .text((d) => d.data.inferred_type || '');
  }

  _handleNodeClick(d) {
    if (this._clickCallback && d.data && d.data.pos) {
      this._clickCallback({ line: d.data.pos.line, col: d.data.pos.col });
    }
  }

  _onNodeClick(callback) {
    this._clickCallback = callback;
  }
}
