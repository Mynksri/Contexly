"""
TreeRenderer â€” Generates interactive HTML+CSS visual tree.

Creates a beautiful, interactive visualization of the codebase tree.
Shows file roles: ENTRY / CORE / UTIL / TEST / SCRIPT / ORPHAN
"""

from pathlib import Path
from typing import Dict
from contexly.core.tree_builder import CodebaseTree


class TreeRenderer:
    """
    Renders an interactive HTML tree visualization.

    Usage:
        renderer = TreeRenderer()
        html = renderer.render(tree)
        renderer.save(tree, "codebase_tree.html")
    """

    LANG_COLORS = {
        "python": "#3572A5",
        "javascript": "#f1e05a",
        "typescript": "#2b7489",
        "go": "#00ADD8",
        "rust": "#dea584",
        "default": "#6e7681",
    }

    # Role badge colors
    ROLE_COLORS = {
        "ENTRY":  "#f0883e",
        "CORE":   "#3fb950",
        "UTIL":   "#58a6ff",
        "TEST":   "#bc8cff",
        "LEGACY": "#ff7b72",
        "SCRIPT": "#8b949e",
        "ORPHAN": "#f85149",
        "UNKNOWN": "#6e7681",
    }

    def render(self, tree: CodebaseTree) -> str:
        nodes_json = self._build_nodes_json(tree)
        stats = self._build_stats(tree)
        return self._html_template(nodes_json, stats, tree.root_path)

    def save(self, tree: CodebaseTree, output_path: str = "contexly_tree.html"):
        html = self.render(tree)
        Path(output_path).write_text(html, encoding="utf-8")
        return output_path

    def _build_nodes_json(self, tree: CodebaseTree) -> str:
        import json
        nodes = []
        for rel_path, node in sorted(tree.nodes.items()):
            lang_color = self.LANG_COLORS.get(node.language, self.LANG_COLORS["default"])
            role = getattr(node, "role", "UNKNOWN")
            role_color = self.ROLE_COLORS.get(role, self.ROLE_COLORS["UNKNOWN"])
            parts = rel_path.replace("\\", "/").split("/")
            nodes.append({
                "path": rel_path,
                "name": parts[-1],
                "dir": "/".join(parts[:-1]) if len(parts) > 1 else "",
                "language": node.language,
                "color": lang_color,
                "role": role,
                "roleColor": role_color,
                "tokens": node.token_estimate,
                "connections": node.connections,
                "importedBy": getattr(node, "imported_by", []),
                "isEntry": getattr(node, "is_entry_point", False),
                "dupeFuncs": getattr(node, "has_duplicate_funcs", []),
                "warnings": getattr(node, "warnings", []),
                "skeleton": node.skeleton_text,
            })
        # Prevent accidental </script> termination inside embedded JSON payload.
        return json.dumps(nodes, ensure_ascii=False).replace("</", "<\\/")

    def _build_stats(self, tree: CodebaseTree) -> dict:
        role_counts: Dict[str, int] = {}
        for node in tree.nodes.values():
            r = getattr(node, "role", "UNKNOWN")
            role_counts[r] = role_counts.get(r, 0) + 1
        return {
            "files": tree.file_count,
            "total_tokens": f"{tree.total_tokens:,}",
            "raw_tokens": f"{tree.raw_token_estimate:,}",
            "reduction": f"{tree.reduction_percent:.1f}%",
            "role_counts": role_counts,
            "entry_files": getattr(tree, "entry_files", []),
            "orphan_files": getattr(tree, "orphan_files", []),
            "project_summary": getattr(tree, "project_summary", ""),
            "core_strategy": getattr(tree, "core_strategy", ""),
            "state_management": getattr(tree, "state_management", ""),
            "state_summaries": getattr(tree, "state_summaries", []),
            "call_graph": getattr(tree, "call_graph", []),
        }

    def _role_counts_html(self, stats: dict) -> str:
        colors = self.ROLE_COLORS
        parts = []
        for role, count in sorted(stats["role_counts"].items()):
            c = colors.get(role, "#6e7681")
            parts.append(
                f'<span style="background:{c};color:#0d1117;border-radius:3px;'
                f'padding:2px 6px;font-size:11px;font-weight:600;">{role}: {count}</span>'
            )
        return " ".join(parts)

    def _html_template(
        self, nodes_json: str, stats: dict, root_path: str
    ) -> str:
        role_badges_html = self._role_counts_html(stats)
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Contexly - Codebase Tree</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0d1117; color: #c9d1d9;
    font-family: 'Segoe UI', system-ui, monospace;
    height: 100vh; display: flex; flex-direction: column;
  }}
  header {{
    background: #161b22; border-bottom: 1px solid #30363d;
    padding: 12px 20px; display: flex; align-items: center; gap: 20px;
  }}
  header h1 {{ color: #58a6ff; font-size: 18px; font-weight: 600; }}
  .stats {{ display: flex; gap: 16px; font-size: 12px; color: #8b949e; }}
  .stat {{ display: flex; flex-direction: column; align-items: center; }}
  .stat-value {{ color: #58a6ff; font-weight: 600; font-size: 14px; }}
  .reduction {{ color: #3fb950 !important; }}
  .container {{ display: flex; flex: 1; overflow: hidden; }}
  #file-tree {{
    width: 280px; min-width: 200px; background: #161b22;
    border-right: 1px solid #30363d; overflow-y: auto; padding: 8px;
  }}
  #main-panel {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
  #search {{
    background: #21262d; border: 1px solid #30363d; border-radius: 6px;
    color: #c9d1d9; padding: 6px 10px; font-size: 13px;
    width: calc(100% - 16px); margin: 8px; outline: none;
  }}
  #search:focus {{ border-color: #58a6ff; }}
  #skeleton-view {{
    flex: 1; padding: 16px; overflow-y: auto; font-family: monospace;
    font-size: 13px; line-height: 1.7; white-space: pre-wrap;
  }}
  .dir-group {{ margin-bottom: 4px; }}
  .dir-label {{
    color: #8b949e; font-size: 11px; padding: 4px 6px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }}
  .file-item {{
    display: flex; align-items: center; gap: 8px;
    padding: 4px 8px; border-radius: 4px; cursor: pointer;
    font-size: 12px; transition: background 0.1s;
  }}
  .file-item:hover {{ background: #21262d; }}
  .file-item.active {{ background: #1f3a5f; color: #58a6ff; }}
  .lang-dot {{
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  }}
  .file-name {{ flex: 1; }}
  .file-tokens {{ color: #6e7681; font-size: 10px; }}
  .skeleton-header {{
    color: #58a6ff; font-weight: 600; margin-bottom: 8px;
    padding-bottom: 6px; border-bottom: 1px solid #30363d;
  }}
  .skeleton-line-calls {{ color: #79c0ff; }}
  .skeleton-line-if {{ color: #ffa657; }}
  .skeleton-line-return {{ color: #3fb950; }}
  .skeleton-line-raise {{ color: #f85149; }}
  .skeleton-line-func {{ color: #d2a8ff; font-weight: 600; }}
  .skeleton-line-import {{ color: #8b949e; }}
  .skeleton-line-class {{ color: #e3b341; font-weight: 600; }}
  .empty-state {{
    flex: 1; display: flex; align-items: center; justify-content: center;
    color: #6e7681; font-size: 14px;
  }}
  .role-badge {{
    font-size: 9px; font-weight: 700; border-radius: 3px;
    padding: 1px 4px; color: #0d1117; flex-shrink: 0;
  }}
  .role-section-header {{
    color: #8b949e; font-size: 10px; padding: 6px 6px 2px;
    text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700;
  }}
  .summary-panel {{
    background:#0f141b; border-bottom:1px solid #30363d; padding:10px 16px;
    font-size:12px; line-height:1.5; color:#9fb3c8;
  }}
  .summary-panel b {{ color:#c9d1d9; }}
</style>
</head>
<body>
<header>
  <h1>&#x27E8;/&#x27E9; Contexly tree</h1>
  <div style="color:#8b949e;font-size:12px;flex:1">{root_path}</div>
  <div class="stats">
    <div class="stat">
      <span class="stat-value">{stats['files']}</span>
      <span>files</span>
    </div>
    <div class="stat">
      <span class="stat-value reduction">{stats['reduction']}</span>
      <span>compressed</span>
    </div>
    <div class="stat">
      <span class="stat-value">{stats['total_tokens']}</span>
      <span>tree tokens</span>
    </div>
    <div class="stat">
      <span class="stat-value" style="color:#f85149">{stats['raw_tokens']}</span>
      <span>raw tokens</span>
    </div>
  </div>
</header>
<div style="background:#161b22;border-bottom:1px solid #30363d;padding:6px 20px;display:flex;flex-wrap:wrap;gap:6px;">
  {role_badges_html}
</div>
<div class="summary-panel">
  <div><b>Summary:</b> {stats.get('project_summary', '')}</div>
  <div><b>Strategy:</b> {stats.get('core_strategy', '')}</div>
  <div><b>State:</b> {stats.get('state_management', '')}</div>
  <div><b>State Flows:</b> {', '.join([s.get('class_name', '') + ' (' + str(s.get('field_count', 0)) + ')' for s in stats.get('state_summaries', [])[:3]])}</div>
  <div><b>Call Graph:</b> {' | '.join(stats.get('call_graph', [])[:3])}</div>
</div>
<div class="container">
  <div id="file-tree">
    <input id="search" placeholder="Search files..." type="text">
    <div id="file-list"></div>
  </div>
  <div id="main-panel">
    <div id="skeleton-view">
      <div class="empty-state">&#8592; Select a file to view its logic skeleton</div>
    </div>
  </div>
</div>
<script>
const NODES = {nodes_json};
const NODE_MAP = Object.fromEntries(NODES.map(n => [n.path, n]));
const fileList = document.getElementById('file-list');
const skeletonView = document.getElementById('skeleton-view');
const search = document.getElementById('search');

function colorLine(line) {{
  if (line.startsWith('FILE:') || line.startsWith('CLASS:')) {{
    return '<span class="skeleton-line-class">' + line + '</span>';
  }} else if (line.startsWith('IMPORTS:')) {{
    return '<span class="skeleton-line-import">' + line + '</span>';
  }} else if (line.match(/^\\s*[~A-Za-z_]/)) {{
    return '<span class="skeleton-line-func">' + line + '</span>';
  }} else if (line.includes('  >')) {{
    return '<span class="skeleton-line-calls">' + line + '</span>';
  }} else if (line.includes('  ?')) {{
    return '<span class="skeleton-line-if">' + line + '</span>';
  }} else if (line.includes('  <')) {{
    return '<span class="skeleton-line-return">' + line + '</span>';
  }} else if (line.includes('  !')) {{
    return '<span class="skeleton-line-raise">' + line + '</span>';
  }}
  return line;
}}

function escapeHtml(str) {{
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function showSkeleton(node) {{
  document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
  const el = document.querySelector('[data-path="' + CSS.escape(node.path) + '"]');
  if (el) el.classList.add('active');
  const coloredLines = node.skeleton.split('\\n').map(l => colorLine(escapeHtml(l))).join('\\n');
  const connsHtml = node.connections.length
    ? '<div style="margin-top:10px;padding-top:8px;border-top:1px solid #30363d;color:#8b949e;font-size:11px;">&#128279; Imports: ' + node.connections.join(', ') + '</div>'
    : '';
  const importedByHtml = node.importedBy && node.importedBy.length
    ? '<div style="margin-top:4px;color:#3fb950;font-size:11px;">&#8593; Imported by: ' + node.importedBy.join(', ') + '</div>'
    : '';
  const dupeHtml = node.dupeFuncs && node.dupeFuncs.length
    ? '<div style="margin-top:4px;color:#f85149;font-size:11px;">&#9888; Duplicate functions: ' + node.dupeFuncs.join(', ') + '</div>'
    : '';
  const roleColor = {{'ENTRY':'#f0883e','CORE':'#3fb950','UTIL':'#58a6ff','TEST':'#bc8cff','LEGACY':'#ff7b72','SCRIPT':'#8b949e','ORPHAN':'#f85149'}}[node.role] || '#6e7681';
  const warnHtml = node.warnings && node.warnings.length
    ? '<div style="margin-top:6px;color:#ff7b72;font-size:11px;">&#9888; ' + node.warnings.join(' | ') + '</div>'
    : '';
  skeletonView.innerHTML =
    '<div class="skeleton-header">&#128196; ' + escapeHtml(node.name)
    + ' &mdash; ' + node.tokens + ' tokens'
    + ' <span style="background:' + roleColor + ';color:#0d1117;border-radius:3px;padding:1px 5px;font-size:10px;font-weight:700;">' + (node.role||'?') + '</span>'
    + '</div>'
    + '<pre>' + coloredLines + '</pre>'
    + connsHtml + importedByHtml + dupeHtml + warnHtml;
}}

function renderFileList(nodes) {{
  const ROLE_ORDER = ['ENTRY','CORE','UTIL','LEGACY','TEST','SCRIPT','ORPHAN','UNKNOWN'];
  const roleColors = {{
    ENTRY:'#f0883e',CORE:'#3fb950',UTIL:'#58a6ff',
    TEST:'#bc8cff',LEGACY:'#ff7b72',SCRIPT:'#8b949e',ORPHAN:'#f85149',UNKNOWN:'#6e7681'
  }};
  const groups = {{}};
  nodes.forEach(n => {{
    const role = n.role || 'UNKNOWN';
    if (!groups[role]) groups[role] = [];
    groups[role].push(n);
  }});
  fileList.innerHTML = '';

  ROLE_ORDER.filter(r => groups[r]).forEach(role => {{
    const group = document.createElement('div');
    group.className = 'dir-group';

    const header = document.createElement('div');
    header.className = 'role-section-header';
    header.style.color = roleColors[role] || '#6e7681';
    header.textContent = 'â–  ' + role;
    group.appendChild(header);

    groups[role].forEach(n => {{
      const item = document.createElement('div');
      item.className = 'file-item';
      item.dataset.path = n.path;
      item.addEventListener('click', () => showSkeleton(n));

      const dot = document.createElement('div');
      dot.className = 'lang-dot';
      dot.style.background = n.color;
      item.appendChild(dot);

      const name = document.createElement('span');
      name.className = 'file-name';
      name.textContent = n.name;
      item.appendChild(name);

      if (n.dupeFuncs && n.dupeFuncs.length) {{
        const warn = document.createElement('span');
        warn.style.color = '#f85149';
        warn.style.fontSize = '10px';
        warn.title = 'Duplicate functions: ' + n.dupeFuncs.join(', ');
        warn.innerHTML = '&#9888;';
        item.appendChild(warn);
      }}

      const tokens = document.createElement('span');
      tokens.className = 'file-tokens';
      tokens.textContent = String(n.tokens) + 't';
      item.appendChild(tokens);

      group.appendChild(item);
    }});

    fileList.appendChild(group);
  }});
}}

search.addEventListener('input', () => {{
  const q = search.value.toLowerCase();
  const filtered = q ? NODES.filter(n =>
    n.path.toLowerCase().includes(q) || n.skeleton.toLowerCase().includes(q)
  ) : NODES;
  renderFileList(filtered);
}});

renderFileList(NODES);
</script>
</body>
</html>"""

