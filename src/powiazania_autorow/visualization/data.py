"""
Data loading and processing for author connection visualization.

This module contains functions for fetching author connections from the database
and preparing node/edge data for visualization.
"""

import math
import random

from bpp.models import Autor

from ..models import AuthorConnection


def get_connections_data(min_connections=1, max_nodes=500):
    """
    Get connection data from database.

    Args:
        min_connections: Minimum number of shared publications to include a connection.
        max_nodes: Maximum number of nodes to include (selects top connected authors).

    Returns:
        Tuple of (author_ids set, connection_data list, author_map dict)
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

    return author_ids, connection_data, author_map


def calculate_positions(author_ids, layout="force"):
    """
    Calculate node positions based on layout algorithm.

    Args:
        author_ids: Set of author IDs
        layout: Layout algorithm to use ("force", "circular", "random")

    Returns:
        Dictionary mapping author_id to {"x": float, "y": float}
    """
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

    return positions


def build_nodes(author_ids, author_map, positions, connection_data):
    """
    Build nodes array for visualization.

    Args:
        author_ids: Set of author IDs
        author_map: Dictionary mapping author_id to full name
        positions: Dictionary mapping author_id to position
        connection_data: List of connection dictionaries

    Returns:
        List of node dictionaries
    """
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

    return nodes


def build_edges(connection_data):
    """
    Build edges array for visualization.

    Args:
        connection_data: List of connection dictionaries

    Returns:
        List of edge dictionaries
    """
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

    return edges


def prepare_visualization_data(min_connections=1, max_nodes=500, layout="force"):
    """
    Prepare all data needed for visualization.

    Args:
        min_connections: Minimum number of shared publications to include.
        max_nodes: Maximum number of nodes to include.
        layout: Layout algorithm to use.

    Returns:
        Tuple of (nodes list, edges list)
    """
    author_ids, connection_data, author_map = get_connections_data(
        min_connections, max_nodes
    )
    positions = calculate_positions(author_ids, layout)
    nodes = build_nodes(author_ids, author_map, positions, connection_data)
    edges = build_edges(connection_data)

    return nodes, edges
