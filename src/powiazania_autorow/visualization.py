"""
Generate Sigma.js visualization for author connections.
"""

import json
import math
import random
from pathlib import Path

from .models import AuthorConnection

from bpp.models import Autor


def generate_sigma_visualization(
    output_path=None, min_connections=1, max_nodes=500, layout="force"
):
    """
    Generate a static JavaScript file with Sigma.js visualization of author connections.

    Args:
        output_path: Path where to save the JS file. If None, returns the JS content.
        min_connections: Minimum number of shared publications to include a connection.
        max_nodes: Maximum number of nodes to include (selects top connected authors).
        layout: Layout algorithm to use ("force", "circular", "random").

    Returns:
        JavaScript content as string if output_path is None, otherwise writes to file.
    """

    # Get all connections meeting the minimum threshold
    connections = AuthorConnection.objects.filter(
        shared_publications_count__gte=min_connections
    ).select_related("primary_author", "secondary_author")

    # Build a set of all authors involved in connections
    author_ids = set()
    connection_data = []

    for conn in connections:
        author_ids.add(conn.primary_author_id)
        author_ids.add(conn.secondary_author_id)
        connection_data.append(
            {
                "source": conn.primary_author_id,
                "target": conn.secondary_author_id,
                "weight": conn.shared_publications_count,
            }
        )

    # If we have too many authors, select the most connected ones
    if len(author_ids) > max_nodes:
        # Count connections per author
        author_connection_counts = {}
        for conn in connection_data:
            author_connection_counts[conn["source"]] = (
                author_connection_counts.get(conn["source"], 0) + 1
            )
            author_connection_counts[conn["target"]] = (
                author_connection_counts.get(conn["target"], 0) + 1
            )

        # Select top authors by connection count
        top_authors = sorted(
            author_connection_counts.items(), key=lambda x: x[1], reverse=True
        )[:max_nodes]
        author_ids = {author_id for author_id, _ in top_authors}

        # Filter connections to only include selected authors
        connection_data = [
            conn
            for conn in connection_data
            if conn["source"] in author_ids and conn["target"] in author_ids
        ]

    # Fetch author details
    authors = Autor.objects.filter(id__in=author_ids).values("id", "imiona", "nazwisko")
    author_map = {
        author["id"]: f"{author['imiona']} {author['nazwisko']}" for author in authors
    }

    # Calculate positions based on layout
    positions = {}

    if layout == "circular":
        # Circular layout
        angle_step = 2 * math.pi / len(author_ids) if author_ids else 1
        radius = 300
        for idx, autor_id in enumerate(sorted(author_ids)):
            angle = idx * angle_step
            positions[autor_id] = {
                "x": radius * math.cos(angle),
                "y": radius * math.sin(angle),
            }
    elif layout == "random":
        # Random layout
        for autor_id in author_ids:
            positions[autor_id] = {
                "x": random.uniform(-400, 400),
                "y": random.uniform(-300, 300),
            }
    else:  # force layout (default)
        # Grid layout as starting position for force
        grid_size = math.ceil(math.sqrt(len(author_ids))) if author_ids else 1
        for idx, autor_id in enumerate(sorted(author_ids)):
            row = idx // grid_size
            col = idx % grid_size
            positions[autor_id] = {
                "x": (col - grid_size / 2) * 50,
                "y": (row - grid_size / 2) * 50,
            }

    # Calculate node sizes based on connection count
    node_connections = {}
    for conn in connection_data:
        node_connections[conn["source"]] = node_connections.get(conn["source"], 0) + 1
        node_connections[conn["target"]] = node_connections.get(conn["target"], 0) + 1

    max_connections = max(node_connections.values()) if node_connections else 1

    # Build nodes array
    nodes = []
    for autor_id in author_ids:
        node_id = str(autor_id)
        connections_count = node_connections.get(autor_id, 1)
        # Size between 10 and 30 based on connections
        size = 10 + (connections_count / max_connections) * 20

        nodes.append(
            {
                "id": node_id,
                "label": author_map.get(autor_id, f"Author {autor_id}"),
                "x": positions[autor_id]["x"],
                "y": positions[autor_id]["y"],
                "size": round(size, 2),
                "color": "#4A90E2",
            }
        )

    # Find max weight for normalization
    max_weight = max((conn["weight"] for conn in connection_data), default=1)

    # Build edges array with proper thickness
    edges = []
    for idx, conn in enumerate(connection_data):
        source_id = str(conn["source"])
        target_id = str(conn["target"])

        # Size between 0.5 and 8 based on weight (more pronounced difference)
        size = 0.5 + (conn["weight"] / max_weight) * 7.5

        # Opacity based on weight
        opacity = min(0.3 + (conn["weight"] / max_weight) * 0.6, 0.9)

        edges.append(
            {
                "id": f"e{idx}",
                "source": source_id,
                "target": target_id,
                "size": round(size, 2),
                "color": f"rgba(100, 100, 100, {round(opacity, 2)})",
                "label": f"{conn['weight']} publikacji",
                "weight": conn["weight"],
            }
        )

    # Generate JavaScript content using Sigma.js v2.4.0 properly
    js_content = f"""// Sigma.js Visualization of Author Connections
// Generated from powiazania_autorow database
// Total authors: {len(nodes)}, Total connections: {len(edges)}

(function() {{
  // Wait for DOM to be ready
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', initializeVisualization);
  }} else {{
    initializeVisualization();
  }}

  function initializeVisualization() {{
    // Check if required libraries are available
    if (typeof Sigma === 'undefined' || typeof graphology === 'undefined') {{
      console.error('Sigma.js or Graphology not loaded. Please include these libraries before this script.');
      return;
    }}

    // Create or get container
    let container = document.getElementById('sigma-container');
    if (!container) {{
      container = document.createElement('div');
      container.id = 'sigma-container';
      container.style.width = '100%';
      container.style.height = '800px';
      container.style.background = 'white';
      container.style.border = '1px solid #ccc';
      container.style.position = 'relative';
      document.body.appendChild(container);
    }}

    // Create a graphology graph
    const graph = new graphology.Graph();

    // Graph data
    const nodes = {json.dumps(nodes, indent=2)};
    const edges = {json.dumps(edges, indent=2)};
    const allEdges = [...edges];  // Store all edges for filtering

    // Track selection state
    let selectedNode = null;
    let neighborNodes = new Set();
    let connectedEdges = new Set();

    // Add nodes to graph
    nodes.forEach(node => {{
      graph.addNode(node.id, {{
        label: node.label,
        x: node.x,
        y: node.y,
        size: node.size,
        color: node.color,
        originalColor: node.color,
        originalSize: node.size
      }});
    }});

    // Add edges to graph
    edges.forEach(edge => {{
      try {{
        graph.addEdge(edge.source, edge.target, {{
          size: edge.size,
          color: edge.color,
          originalColor: edge.color,
          originalSize: edge.size,
          label: edge.label,
          weight: edge.weight
        }});
      }} catch (e) {{
        console.warn('Could not add edge:', e.message);
      }}
    }});

    // Create Sigma instance with custom node and edge programs
    const sigmaInstance = new Sigma(graph, container, {{
      renderEdgeLabels: true,
      defaultNodeColor: '#4A90E2',
      defaultEdgeColor: '#999',
      labelSize: 12,
      labelColor: {{ color: '#000' }},
      edgeLabelSize: 10,
      minNodeSize: 5,
      maxNodeSize: 30,
      minEdgeSize: 0.5,
      maxEdgeSize: 10,
      mouseWheelEnabled: true,
      doubleClickZoomingRatio: 2,
      zoomMin: 0.1,
      zoomMax: 10,

      // Custom node reducer for highlighting
      nodeReducer: (node, data) => {{
        const res = {{ ...data }};

        if (selectedNode) {{
          if (node === selectedNode) {{
            res.color = '#FF6B6B';  // Red for selected
            res.highlighted = true;
          }} else if (neighborNodes.has(node)) {{
            res.color = '#FFA500';  // Orange for neighbors
            res.highlighted = true;
          }} else {{
            res.color = '#D3D3D3';  // Gray for others
            res.hidden = false;
          }}
        }}

        return res;
      }},

      // Custom edge reducer for highlighting
      edgeReducer: (edge, data) => {{
        const res = {{ ...data }};

        if (selectedNode && connectedEdges.has(edge)) {{
          res.color = 'rgba(255, 107, 107, 0.9)';
          res.size = data.originalSize * 2;
          res.hidden = false;
        }} else if (selectedNode) {{
          res.color = 'rgba(200, 200, 200, 0.1)';
          res.hidden = false;
        }}

        return res;
      }}
    }});

    // Function to highlight node and its neighbors
    function selectNode(nodeId) {{
      selectedNode = nodeId;
      neighborNodes.clear();
      connectedEdges.clear();

      // Find neighbors and connected edges
      graph.forEachNeighbor(nodeId, (neighbor) => {{
        neighborNodes.add(neighbor);
      }});

      graph.forEachEdge(nodeId, (edge) => {{
        connectedEdges.add(edge);
      }});

      // Trigger re-render
      sigmaInstance.refresh();

      // Update info display
      updateSelectionInfo(nodeId);
    }}

    // Function to clear selection
    function clearSelection() {{
      selectedNode = null;
      neighborNodes.clear();
      connectedEdges.clear();
      sigmaInstance.refresh();

      const selectionPanel = document.getElementById('selection-info');
      if (selectionPanel) {{
        selectionPanel.style.display = 'none';
      }}
    }}

    // Function to update selection info
    function updateSelectionInfo(nodeId) {{
      const nodeData = graph.getNodeAttributes(nodeId);
      let infoText = `<strong>Wybrany autor:</strong> ${{nodeData.label}}<br>`;
      infoText += `<strong>Połączonych autorów:</strong> ${{neighborNodes.size}}<br>`;

      if (neighborNodes.size > 0 && neighborNodes.size <= 10) {{
        infoText += '<strong>Połączeni z:</strong><br>';
        neighborNodes.forEach(neighborId => {{
          const neighborData = graph.getNodeAttributes(neighborId);
          const edgeId = graph.edge(nodeId, neighborId) || graph.edge(neighborId, nodeId);
          if (edgeId) {{
            const edgeData = graph.getEdgeAttributes(edgeId);
            infoText += `• ${{neighborData.label}} (${{edgeData.weight}} publikacji)<br>`;
          }}
        }});
      }}

      // Update or create selection info panel
      let selectionPanel = document.getElementById('selection-info');
      if (!selectionPanel) {{
        selectionPanel = document.createElement('div');
        selectionPanel.id = 'selection-info';
        selectionPanel.style.position = 'absolute';
        selectionPanel.style.bottom = '10px';
        selectionPanel.style.right = '10px';
        selectionPanel.style.padding = '10px';
        selectionPanel.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
        selectionPanel.style.border = '1px solid #ddd';
        selectionPanel.style.borderRadius = '4px';
        selectionPanel.style.fontSize = '12px';
        selectionPanel.style.maxWidth = '300px';
        selectionPanel.style.zIndex = '1001';
        container.appendChild(selectionPanel);
      }}
      selectionPanel.innerHTML = infoText;
      selectionPanel.style.display = 'block';
    }}

    // Bind click events
    sigmaInstance.on('clickNode', ({{ node }}) => {{
      if (selectedNode === node) {{
        clearSelection();
      }} else {{
        selectNode(node);
      }}
    }});

    sigmaInstance.on('clickStage', () => {{
      clearSelection();
    }});

    // Add info panel
    const infoPanel = document.createElement('div');
    infoPanel.style.position = 'absolute';
    infoPanel.style.top = '10px';
    infoPanel.style.left = '10px';
    infoPanel.style.padding = '10px';
    infoPanel.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
    infoPanel.style.border = '1px solid #ddd';
    infoPanel.style.borderRadius = '4px';
    infoPanel.style.fontSize = '12px';
    infoPanel.style.zIndex = '1000';
    infoPanel.innerHTML = `
      <strong>Wizualizacja powiązań autorów</strong><br>
      Liczba autorów: {len(nodes)}<br>
      Liczba połączeń: {len(edges)}<br>
      Min. wspólnych publikacji: {min_connections}<br>
      Układ: {layout}<br>
      <br>
      <em>Kliknij na autora aby zobaczyć połączenia</em><br>
      <em>Grubość linii = liczba wspólnych publikacji</em>
    `;
    container.appendChild(infoPanel);

    // Add zoom controls and filter
    const controls = document.createElement('div');
    controls.style.position = 'absolute';
    controls.style.top = '10px';
    controls.style.right = '10px';
    controls.style.zIndex = '1000';
    controls.innerHTML = `
      <button id="zoom-in" style="display: block; margin: 5px; padding: 8px 12px; background: #4A90E2;
      color: white; border: none; border-radius: 3px; cursor: pointer;">+</button>
      <button id="zoom-out" style="display: block; margin: 5px; padding: 8px 12px; background: #4A90E2;
      color: white; border: none; border-radius: 3px; cursor: pointer;">−</button>
      <button id="zoom-reset" style="display: block; margin: 5px; padding: 8px 12px; background: #4A90E2;
      color: white; border: none; border-radius: 3px; cursor: pointer;">⟲</button>
      <div style="margin: 10px 5px; padding: 10px; background: rgba(255,255,255,0.9); border-radius: 3px;">
        <label style="display: flex; align-items: center; font-size: 12px; cursor: pointer;">
          <input type="checkbox" id="filter-single" style="margin-right: 5px;">
          <span>Ukryj połączenia<br>z 1 publikacją</span>
        </label>
      </div>
    `;
    container.appendChild(controls);

    // Zoom controls
    document.getElementById('zoom-in').addEventListener('click', () => {{
      const camera = sigmaInstance.getCamera();
      const currentRatio = camera.getState().ratio;
      camera.setState({{ ratio: currentRatio / 1.5 }});
    }});

    document.getElementById('zoom-out').addEventListener('click', () => {{
      const camera = sigmaInstance.getCamera();
      const currentRatio = camera.getState().ratio;
      camera.setState({{ ratio: currentRatio * 1.5 }});
    }});

    document.getElementById('zoom-reset').addEventListener('click', () => {{
      const camera = sigmaInstance.getCamera();
      camera.setState({{ x: 0.5, y: 0.5, ratio: 1 }});
    }});

    // Filter toggle handler
    document.getElementById('filter-single').addEventListener('change', function(e) {{
      const filterSingle = e.target.checked;

      // Clear selection first
      clearSelection();

      // Clear the graph
      graph.clear();

      // Re-add nodes
      nodes.forEach(node => {{
        graph.addNode(node.id, {{
          label: node.label,
          x: node.x,
          y: node.y,
          size: node.size,
          color: node.color,
          originalColor: node.color,
          originalSize: node.size
        }});
      }});

      // Filter and re-add edges
      const edgesToAdd = filterSingle ?
        allEdges.filter(edge => (edge.weight || 1) > 1) :
        allEdges;

      edgesToAdd.forEach(edge => {{
        try {{
          graph.addEdge(edge.source, edge.target, {{
            size: edge.size,
            color: edge.color,
            originalColor: edge.color,
            originalSize: edge.size,
            label: edge.label,
            weight: edge.weight
          }});
        }} catch (e) {{
          console.warn('Could not add edge:', e.message);
        }}
      }});

      // Update info panel
      const edgeCount = graph.size;
      infoPanel.innerHTML = infoPanel.innerHTML.replace(
        /Liczba połączeń(?: \\(filtrowane\\))?: \\d+/,
        `Liczba połączeń${{filterSingle ? ' (filtrowane)' : ''}}: ${{edgeCount}}`
      );

      // Refresh the visualization
      sigmaInstance.refresh();

      console.log(`Filter applied: ${{filterSingle ? 'hiding' : 'showing'}} single-publication connections`);
      console.log(`Edges displayed: ${{edgeCount}} / ${{allEdges.length}}`);
    }});

    // Export to global scope
    window.sigmaInstance = sigmaInstance;
    window.authorGraph = graph;
    window.selectNode = selectNode;
    window.clearSelection = clearSelection;

    console.log('Author connections visualization loaded successfully');
    console.log('Nodes:', graph.order, 'Edges:', graph.size);
  }}
}})();
"""

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(js_content, encoding="utf-8")
        return f"Visualization saved to {output_path}"
    else:
        return js_content


def generate_visualization_html(
    output_path=None, min_connections=2, max_nodes=300, layout="force"
):
    """
    Generate a standalone HTML file with Sigma.js visualization.

    Args:
        output_path: Path where to save the HTML file. If None, returns the HTML content.
        min_connections: Minimum number of shared publications to include.
        max_nodes: Maximum number of nodes to include.
        layout: Layout algorithm to use.

    Returns:
        HTML content as string if output_path is None, otherwise writes to file.
    """

    # Generate the visualization JavaScript
    js_content = generate_sigma_visualization(
        min_connections=min_connections, max_nodes=max_nodes, layout=layout
    )

    html_content = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wizualizacja powiązań autorów - BPP</title>

    <!-- Sigma.js v2.4.0 and Graphology -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/sigma.js/2.4.0/sigma.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/graphology/0.25.4/graphology.umd.min.js"></script>

    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            background: #f5f5f5;
        }}

        #sigma-container {{
            width: 100vw;
            height: 100vh;
            background: white;
            position: relative;
        }}

        .controls-panel {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(255, 255, 255, 0.95);
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
            width: 200px;
        }}

        .controls-panel h3 {{
            margin-top: 0;
            margin-bottom: 15px;
            font-size: 16px;
            color: #333;
        }}

        .controls-panel button {{
            display: block;
            width: 100%;
            margin: 5px 0;
            padding: 8px 12px;
            background: #4A90E2;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }}

        .controls-panel button:hover {{
            background: #357ABD;
        }}

        .search-box {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #ddd;
        }}

        .search-box input {{
            width: 100%;
            padding: 6px 8px;
            border: 1px solid #ddd;
            border-radius: 3px;
            font-size: 13px;
            box-sizing: border-box;
        }}

        .search-results {{
            margin-top: 10px;
            max-height: 200px;
            overflow-y: auto;
            font-size: 12px;
        }}

        .search-result-item {{
            padding: 5px;
            cursor: pointer;
            border-radius: 3px;
            transition: background 0.2s;
        }}

        .search-result-item:hover {{
            background: #e0e0e0;
        }}

        .loader {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 18px;
            color: #666;
        }}

        .legend {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(255, 255, 255, 0.95);
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}

        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div id="sigma-container">
        <div class="loader">Ładowanie wizualizacji...</div>
    </div>

    <div class="controls-panel">
        <h3>Kontrolki</h3>
        <button onclick="resetView()">Resetuj widok</button>
        <button onclick="toggleEdgeLabels()">Etykiety krawędzi</button>

        <div style="margin: 15px 0; padding: 10px; background: #f0f0f0; border-radius: 3px;">
            <label style="display: flex; align-items: center; font-size: 13px; cursor: pointer;">
                <input type="checkbox" id="filter-single-html" style="margin-right: 5px;"
                onchange="filterSingleConnections(this.checked)">
                <span>Ukryj połączenia z tylko 1 publikacją</span>
            </label>
        </div>

        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Szukaj autora..." onkeyup="searchAuthors(this.value)">
            <div id="searchResults" class="search-results"></div>
        </div>
    </div>

    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #4A90E2;"></div>
            <span>Autor</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #FF6B6B;"></div>
            <span>Wybrany autor</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #FFA500;"></div>
            <span>Połączony autor</span>
        </div>
        <div class="legend-item">
            <div style="width: 20px; height: 2px; background: #666; margin-right: 8px;"></div>
            <span>Grubość = liczba publikacji</span>
        </div>
    </div>

    <script>
        let showEdgeLabels = true;
        let searchTimeout = null;

        // Hide loader when ready
        window.addEventListener('load', function() {{
            setTimeout(function() {{
                const loader = document.querySelector('.loader');
                if (loader) loader.style.display = 'none';
            }}, 500);
        }});

        function resetView() {{
            if (window.sigmaInstance) {{
                const camera = window.sigmaInstance.getCamera();
                camera.setState({{ x: 0.5, y: 0.5, ratio: 1 }});
            }}
        }}

        function toggleEdgeLabels() {{
            showEdgeLabels = !showEdgeLabels;
            if (window.sigmaInstance) {{
                window.sigmaInstance.setSetting('renderEdgeLabels', showEdgeLabels);
            }}
        }}

        function searchAuthors(query) {{
            clearTimeout(searchTimeout);
            const resultsDiv = document.getElementById('searchResults');

            if (!query || query.length < 2) {{
                resultsDiv.innerHTML = '';
                return;
            }}

            searchTimeout = setTimeout(() => {{
                if (!window.authorGraph) return;

                const results = [];
                const lowerQuery = query.toLowerCase();

                window.authorGraph.forEachNode((node, attrs) => {{
                    if (attrs.label.toLowerCase().includes(lowerQuery)) {{
                        results.push({{ id: node, label: attrs.label }});
                    }}
                }});

                // Display results
                if (results.length > 0) {{
                    resultsDiv.innerHTML = results.slice(0, 10).map(r =>
                        `<div class="search-result-item" onclick="focusNode('${{r.id}}')">${{r.label}}</div>`
                    ).join('');
                }} else {{
                    resultsDiv.innerHTML = '<div style="padding: 5px; color: #999;">Nie znaleziono autorów</div>';
                }}
            }}, 300);
        }}

        function focusNode(nodeId) {{
            if (window.sigmaInstance && window.authorGraph) {{
                const nodeData = window.authorGraph.getNodeAttributes(nodeId);
                if (nodeData) {{
                    // Focus camera on node
                    const camera = window.sigmaInstance.getCamera();
                    const {{ x, y }} = window.sigmaInstance.graphToViewport({{ x: nodeData.x, y: nodeData.y }});
                    camera.setState({{
                        x: 0.5 + (0.5 - x / container.offsetWidth),
                        y: 0.5 + (0.5 - y / container.offsetHeight),
                        ratio: 0.5
                    }});

                    // Select the node
                    setTimeout(() => {{
                        if (window.selectNode) {{
                            window.selectNode(nodeId);
                        }}
                    }}, 300);
                }}

                // Clear search
                document.getElementById('searchInput').value = '';
                document.getElementById('searchResults').innerHTML = '';
            }}
        }}

        function filterSingleConnections(filterEnabled) {{
            // Trigger the filter on the embedded visualization
            const filterCheckbox = document.querySelector('#filter-single');
            if (filterCheckbox) {{
                filterCheckbox.checked = filterEnabled;
                filterCheckbox.dispatchEvent(new Event('change'));
            }}
        }}
    </script>

    <!-- Visualization Script -->
    <script>
        {js_content}
    </script>
</body>
</html>"""

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding="utf-8")
        return f"HTML visualization saved to {output_path}"
    else:
        return html_content
