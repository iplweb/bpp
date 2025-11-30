"""
JavaScript generation for Sigma.js author connection visualization.
"""

import json
from pathlib import Path

from .data import prepare_visualization_data


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
    nodes, edges = prepare_visualization_data(min_connections, max_nodes, layout)

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
