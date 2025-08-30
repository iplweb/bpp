"""
Generate OGMA visualization for author connections.
"""

import json
import math
from pathlib import Path

from .models import AuthorConnection

from bpp.models import Autor


def generate_ogma_visualization(output_path=None, min_connections=1, max_nodes=500):
    """
    Generate a static JavaScript file with OGMA visualization of author connections.

    Args:
        output_path: Path where to save the JS file. If None, returns the JS content.
        min_connections: Minimum number of shared publications to include a connection.
        max_nodes: Maximum number of nodes to include (selects top connected authors).

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

    # Create node ID mapping (OGMA prefers sequential integer IDs)
    id_mapping = {autor_id: idx for idx, autor_id in enumerate(sorted(author_ids))}

    # Calculate node positions using force-directed layout simulation
    nodes = []
    edges = []

    # Simple circular layout as starting positions
    angle_step = 2 * math.pi / len(author_ids)
    radius = 500

    for autor_id in sorted(author_ids):
        node_id = id_mapping[autor_id]
        angle = node_id * angle_step
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)

        nodes.append(
            {
                "id": node_id,
                "attributes": {
                    "text": author_map.get(autor_id, f"Author {autor_id}"),
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "radius": 10,  # Base radius, can be adjusted based on connections
                },
            }
        )

    # Find max weight for normalization
    max_weight = max((conn["weight"] for conn in connection_data), default=1)

    # Create edges with thickness based on shared publications
    for conn in connection_data:
        source_id = id_mapping.get(conn["source"])
        target_id = id_mapping.get(conn["target"])

        if source_id is not None and target_id is not None:
            # Normalize width between 0.5 and 5
            width = 0.5 + (conn["weight"] / max_weight) * 4.5

            edges.append(
                {
                    "source": source_id,
                    "target": target_id,
                    "attributes": {
                        "width": round(width, 2),
                        "color": f"rgba(100, 100, 100, {min(0.8, 0.2 + conn['weight']/max_weight*0.6)})",
                        "label": (
                            f"{conn['weight']} publikacji"
                            if conn["weight"] > 5
                            else None
                        ),
                    },
                }
            )

    # Generate JavaScript content
    js_content = f"""// OGMA Visualization of Author Connections
// Generated from powiazania_autorow database
// Total authors: {len(nodes)}, Total connections: {len(edges)}

// This script assumes OGMA is loaded (either via CDN or local installation)
// Example CDN: <script src="https://cdn.jsdelivr.net/npm/@linkurious/ogma@4/dist/ogma.min.js"></script>

(async function() {{
  // Check if OGMA is available
  if (typeof Ogma === 'undefined') {{
    console.error('OGMA library is not loaded. Please include OGMA before this script.');
    return;
  }}

  // Create container if it doesn't exist
  let container = document.getElementById('graph-container');
  if (!container) {{
    container = document.createElement('div');
    container.id = 'graph-container';
    container.style.width = '100%';
    container.style.height = '800px';
    container.style.border = '1px solid #ccc';
    document.body.appendChild(container);
  }}

  // Initialize OGMA
  const ogma = new Ogma({{
    container: 'graph-container',
    options: {{
      backgroundColor: '#ffffff'
    }}
  }});

  // Graph data
  const graphData = {{
    nodes: {json.dumps(nodes, indent=2)},
    edges: {json.dumps(edges, indent=2)}
  }};

  // Set the graph
  await ogma.setGraph(graphData);

  // Apply force-directed layout for better positioning
  if (ogma.layouts && ogma.layouts.force) {{
    await ogma.layouts.force({{
      duration: 2000,
      gpu: true,  // Use GPU acceleration if available
      settings: {{
        gravity: 0.05,
        charge: -1000,
        springLength: 100,
        springCoefficient: 0.01,
        theta: 0.8
      }}
    }});
  }}

  // Style the nodes and edges
  ogma.styles.setNodeStyle({{
    color: '#4A90E2',
    radius: 12,
    strokeColor: '#2E5C8A',
    strokeWidth: 2,
    text: {{
      font: '12px Arial, sans-serif',
      color: '#333333',
      backgroundColor: 'rgba(255, 255, 255, 0.8)',
      padding: 2,
      minVisibleSize: 10
    }}
  }});

  ogma.styles.setEdgeStyle({{
    color: 'rgba(150, 150, 150, 0.5)',
    shape: 'line'
  }});

  // Enable interactions
  ogma.events.on('click', function(evt) {{
    if (evt.target && evt.target.isNode) {{
      const node = evt.target;
      const connectedEdges = node.getAdjacentEdges();
      const connectedNodes = node.getAdjacentNodes();

      // Highlight selected node and its connections
      ogma.styles.setSelectedNodeStyle({{
        color: '#FF6B6B',
        radius: 15
      }});

      node.setSelected(true);
      connectedEdges.setSelected(true);
      connectedNodes.setSelected(true);

      console.log('Selected author:', node.getData('text'));
      console.log('Connections:', connectedNodes.size);
    }}
  }});

  // Add zoom controls
  ogma.view.setZoom(0.8);

  // Center the graph
  await ogma.view.locateGraph({{
    duration: 1000,
    padding: 50
  }});

  // Add basic controls info
  const info = document.createElement('div');
  info.style.position = 'absolute';
  info.style.top = '10px';
  info.style.left = '10px';
  info.style.padding = '10px';
  info.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
  info.style.border = '1px solid #ddd';
  info.style.borderRadius = '4px';
  info.style.fontSize = '12px';
  info.innerHTML = `
    <strong>Wizualizacja powiązań autorów</strong><br>
    Liczba autorów: {len(nodes)}<br>
    Liczba połączeń: {len(edges)}<br>
    Min. wspólnych publikacji: {min_connections}<br>
    <br>
    <em>Kliknij na autora aby podświetlić połączenia</em>
  `;
  container.appendChild(info);

  console.log('Author connections visualization loaded successfully');
}})();
"""

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(js_content, encoding="utf-8")
        return f"Visualization saved to {output_path}"
    else:
        return js_content


def generate_visualization_html(output_path=None):
    """
    Generate a standalone HTML file with OGMA visualization.

    Args:
        output_path: Path where to save the HTML file. If None, returns the HTML content.

    Returns:
        HTML content as string if output_path is None, otherwise writes to file.
    """

    # Generate the visualization JavaScript
    js_content = generate_ogma_visualization()

    html_content = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wizualizacja powiązań autorów - BPP</title>

    <!-- OGMA CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@linkurious/ogma@4/dist/ogma.min.css">

    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: Arial, sans-serif;
            overflow: hidden;
        }}

        #graph-container {{
            width: 100vw;
            height: 100vh;
            position: relative;
        }}

        .controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(255, 255, 255, 0.95);
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }}

        .controls button {{
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
        }}

        .controls button:hover {{
            background: #357ABD;
        }}

        .loader {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 18px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div id="graph-container">
        <div class="loader">Ładowanie wizualizacji...</div>
    </div>

    <div class="controls">
        <h3 style="margin-top: 0;">Kontrolki</h3>
        <button onclick="if(window.ogma) ogma.view.locateGraph()">Wycentruj graf</button>
        <button onclick="if(window.ogma) ogma.view.zoomIn()">Przybliż</button>
        <button onclick="if(window.ogma) ogma.view.zoomOut()">Oddal</button>
        <button onclick="if(window.ogma) ogma.clearSelection()">Wyczyść zaznaczenie</button>
    </div>

    <!-- OGMA Library -->
    <script src="https://cdn.jsdelivr.net/npm/@linkurious/ogma@4/dist/ogma.min.js"></script>

    <!-- Visualization Script -->
    <script>
        // Hide loader when visualization is ready
        window.addEventListener('load', function() {{
            setTimeout(function() {{
                const loader = document.querySelector('.loader');
                if (loader) loader.style.display = 'none';
            }}, 2000);
        }});

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
