"""
HTML generation for Sigma.js author connection visualization.
"""

from pathlib import Path

from .js import generate_sigma_visualization


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
