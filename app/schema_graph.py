"""Schema Graph module for SchemaScout.

Constructs a NetworkX graph of database tables connected by foreign-key relationships.
Finds shortest paths between tables to expand seed tables with necessary bridge tables,
and computes foreign-key join hints.
"""

from itertools import combinations
from typing import Any
import networkx as nx
from app.schema_loader import SchemaInfo, load_schema
from app import config


class SchemaGraph:
    """Graph representation of database schema foreign-key relationships."""

    def __init__(self, schema_info: SchemaInfo | None = None) -> None:
        self.schema_info = schema_info or load_schema()
        self.graph = nx.Graph()
        self._build_graph()

    def _build_graph(self) -> None:
        """Populates the graph nodes (tables) and edges (FK relationships)."""
        for tbl_name in self.schema_info.get_table_names():
            self.graph.add_node(tbl_name)

        for table_a, col_a, table_b, col_b in self.schema_info.fk_relationships:
            if not self.graph.has_edge(table_a, table_b):
                self.graph.add_edge(table_a, table_b, joins=[])
            edge_data = self.graph.get_edge_data(table_a, table_b)
            join_cond = f"{table_a}.{col_a} = {table_b}.{col_b}"
            if join_cond not in edge_data["joins"]:
                edge_data["joins"].append(join_cond)

    def expand_with_join_paths(
        self,
        seed_tables: list[str],
        max_tables: int | None = None,
    ) -> tuple[list[str], list[str]]:
        """Expands a list of seed tables with bridge tables found along shortest paths.

        Args:
            seed_tables: Initial list of semantically retrieved tables.
            max_tables: Maximum total tables after expansion. Defaults to config.MAX_TABLES_AFTER_EXPANSION.

        Returns:
            Tuple of (all_tables, bridge_tables).
        """
        cap = max_tables or config.MAX_TABLES_AFTER_EXPANSION
        final_tables: list[str] = []
        bridge_tables: list[str] = []

        # Keep original seed tables in their order, up to cap
        for tbl in seed_tables:
            if tbl in self.graph and tbl not in final_tables:
                final_tables.append(tbl)
                if len(final_tables) >= cap:
                    return final_tables, bridge_tables

        # Check all pairs of seed tables for connecting paths
        discovered_bridges: list[str] = []
        for u, v in combinations(seed_tables, 2):
            if u in self.graph and v in self.graph and nx.has_path(self.graph, u, v):
                path = nx.shortest_path(self.graph, source=u, target=v)
                # Intermediate nodes in the shortest path are bridges
                for node in path[1:-1]:
                    if node not in final_tables and node not in discovered_bridges:
                        discovered_bridges.append(node)

        # Add bridge tables up to cap
        for bridge in discovered_bridges:
            if len(final_tables) < cap:
                final_tables.append(bridge)
                bridge_tables.append(bridge)
            else:
                break

        return final_tables, bridge_tables

    def get_join_hints(self, tables: list[str]) -> list[str]:
        """Returns string join conditions for every foreign-key edge among the given tables.

        Example:
            ["Invoice.CustomerId = Customer.CustomerId"]
        """
        table_set = set(tables)
        hints: list[str] = []
        seen: set[str] = set()

        for u, v in combinations(tables, 2):
            if self.graph.has_edge(u, v):
                edge_data = self.graph.get_edge_data(u, v)
                for join_cond in edge_data.get("joins", []):
                    if join_cond not in seen:
                        seen.add(join_cond)
                        hints.append(join_cond)

        return hints


def build_schema_graph(schema_info: SchemaInfo | None = None) -> SchemaGraph:
    """Convenience factory for SchemaGraph."""
    return SchemaGraph(schema_info=schema_info)


def expand_with_join_paths(
    seed_tables: list[str],
    max_tables: int | None = None,
    schema_info: SchemaInfo | None = None,
) -> list[str]:
    """Helper returning final expanded table list."""
    graph = SchemaGraph(schema_info=schema_info)
    all_tables, _ = graph.expand_with_join_paths(seed_tables=seed_tables, max_tables=max_tables)
    return all_tables


def get_join_hints(tables: list[str], schema_info: SchemaInfo | None = None) -> list[str]:
    """Helper returning join hints for a list of tables."""
    graph = SchemaGraph(schema_info=schema_info)
    return graph.get_join_hints(tables=tables)
