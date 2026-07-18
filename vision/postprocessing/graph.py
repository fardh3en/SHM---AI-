"""
Interface and placeholder implementation for the Crack Graph Topology Builder.

Advanced topology (junction kernels, segment BFS paths, and NetworkX metrics)
is deferred to Phase 3 (Structural Health Intelligence).
"""
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

try:
    import networkx as nx
    _NETWORKX_AVAILABLE = True
except ImportError:
    _NETWORKX_AVAILABLE = False


class ICrackGraphBuilder(ABC):
    """
    Interface for building topological graph representations from crack skeletons.
    """

    @abstractmethod
    def build_graph(self, skeleton_mask: np.ndarray) -> Any:
        """
        Analyze a centerline skeleton and construct a topology graph.

        Args:
            skeleton_mask: Binary centerline skeleton [H, W] with values in {0, 255}.

        Returns:
            A networkx.Graph representing junctions as nodes and segments as edges.
        """
        pass


class PlaceholderGraphBuilder(ICrackGraphBuilder):
    """
    A minimal, placeholder implementation of ICrackGraphBuilder for Phase 2.
    
    Provides basic interface compliance. Returns a networkx.Graph with a single
    node or simple coordinates to prevent pipeline breakdown.
    """

    def __init__(self) -> None:
        if not _NETWORKX_AVAILABLE:
            raise ImportError(
                "networkx is required for PlaceholderGraphBuilder. "
                "Install it using pip install -e '.[vision]'"
            )

    def build_graph(self, skeleton_mask: np.ndarray) -> Any:
        """
        Build a placeholder graph containing the coordinates of non-zero pixels.
        """
        graph = nx.Graph()

        # Find skeleton pixels
        pixels = np.argwhere(skeleton_mask > 0)
        
        if len(pixels) == 0:
            return graph

        # Just add endpoints (first and last pixel of skeleton) as a placeholder node representation
        start_node = tuple(pixels[0])
        end_node = tuple(pixels[-1])

        graph.add_node(start_node, type="endpoint")
        graph.add_node(end_node, type="endpoint")
        
        # Connect them with a placeholder edge
        # Path is simply the start and end coordinates
        graph.add_edge(start_node, end_node, path=[start_node, end_node])

        return graph
