"""
Visualization package for author connections.

This module re-exports all visualization functions for backward compatibility.
"""

from .data import (
    build_edges,
    build_nodes,
    calculate_positions,
    get_connections_data,
    prepare_visualization_data,
)
from .html import generate_visualization_html
from .js import generate_sigma_visualization

__all__ = [
    # Main functions
    "generate_sigma_visualization",
    "generate_visualization_html",
    # Data functions
    "get_connections_data",
    "calculate_positions",
    "build_nodes",
    "build_edges",
    "prepare_visualization_data",
]
