// BPP Author Connections Visualization UI
// Provides UI controls for author network visualization

if (window.bpp == undefined) window.bpp = {};

window.bpp.authorConnections = {
    showEdgeLabels: true,
    searchTimeout: null,

    resetView: function() {
        if (window.sigmaInstance) {
            const camera = window.sigmaInstance.getCamera();
            camera.setState({ x: 0.5, y: 0.5, ratio: 1 });
        }
    },

    toggleEdgeLabels: function() {
        this.showEdgeLabels = !this.showEdgeLabels;
        if (window.sigmaInstance) {
            window.sigmaInstance.setSetting('renderEdgeLabels', this.showEdgeLabels);
        }
    },

    searchAuthors: function(query) {
        var self = this;
        clearTimeout(self.searchTimeout);
        var resultsDiv = document.getElementById('searchResults');

        if (!query || query.length < 2) {
            resultsDiv.innerHTML = '';
            return;
        }

        self.searchTimeout = setTimeout(function() {
            if (!window.authorGraph) return;

            var results = [];
            var lowerQuery = query.toLowerCase();

            window.authorGraph.forEachNode(function(node, attrs) {
                if (attrs.label.toLowerCase().includes(lowerQuery)) {
                    results.push({ id: node, label: attrs.label });
                }
            });

            if (results.length > 0) {
                resultsDiv.innerHTML = results.slice(0, 10).map(function(r) {
                    return '<div class="search-result-item" onclick="window.bpp.authorConnections.focusNode(\'' + r.id + '\')">' + r.label + '</div>';
                }).join('');
            } else {
                resultsDiv.innerHTML = '<div style="padding: 5px; color: #999;">Nie znaleziono autorów</div>';
            }
        }, 300);
    },

    focusNode: function(nodeId) {
        if (window.sigmaInstance && window.authorGraph) {
            var nodeData = window.authorGraph.getNodeAttributes(nodeId);
            if (nodeData) {
                var container = document.getElementById('sigma-container');
                if (container) {
                    var camera = window.sigmaInstance.getCamera();
                    var position = window.sigmaInstance.graphToViewport({ x: nodeData.x, y: nodeData.y });
                    camera.setState({
                        x: 0.5 + (0.5 - position.x / container.offsetWidth),
                        y: 0.5 + (0.5 - position.y / container.offsetHeight),
                        ratio: 0.5
                    });
                }

                setTimeout(function() {
                    if (window.selectNode) {
                        window.selectNode(nodeId);
                    }
                }, 300);
            }

            var searchInput = document.getElementById('searchInput');
            var searchResults = document.getElementById('searchResults');
            if (searchInput) searchInput.value = '';
            if (searchResults) searchResults.innerHTML = '';
        }
    },

    filterSingleConnections: function(filterEnabled) {
        var filterCheckbox = document.querySelector('#filter-single');
        if (filterCheckbox) {
            filterCheckbox.checked = filterEnabled;
            filterCheckbox.dispatchEvent(new Event('change'));
        }
    }
};
