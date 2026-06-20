"""
graph.py — Property Graph for Fraud Transaction Network
========================================================
Builds a directed property graph of banking transactions using networkx.

Node types:
  customer    — one node per unique customer_id
  transaction — one node per transaction with all fields + optional risk attrs
  location    — one node per unique location string

Edge types:
  MADE        — Customer → Transaction
  AT_LOCATION — Transaction → Location
  FOLLOWS     — Transaction → Transaction (same customer, ≤ RAPID_TXN_WINDOW_SEC)
"""

import networkx as nx
from config.settings import config
from core.rules import _parse_time

# Indian city/country keywords — must mirror the list in rules.py
_DOMESTIC_KEYWORDS = [
    "india", "mumbai", "delhi", "bangalore", "bengaluru", "chennai",
    "hyderabad", "pune", "ahmedabad", "kolkata", "jaipur", "surat",
    "lucknow", "kanpur", "nagpur", "visakhapatnam", "indore", "bhopal",
]


def _location_risk(location: str) -> int:
    loc_lower = location.lower()
    for fraud_kw in config.FRAUD_LOCATIONS:
        if fraud_kw in loc_lower:
            return 80
    for dom_kw in _DOMESTIC_KEYWORDS:
        if dom_kw in loc_lower:
            return 20
    return 50


def build_fraud_graph(
    transactions: list,
    analysis_results: list | None = None,
) -> nx.DiGraph:
    """Build a directed property graph from a list of transaction dicts.

    If analysis_results (list of orchestrator result dicts) is provided,
    Transaction nodes are enriched with risk_level, risk_score, fraud_reasons.
    """
    G = nx.DiGraph()

    # Index analysis results by transaction_id for O(1) lookup
    result_map: dict = {}
    if analysis_results:
        for r in analysis_results:
            tid = r.get("transaction_id")
            if tid:
                result_map[tid] = r

    # ── Pass 1: Add all nodes and MADE / AT_LOCATION edges ──────────
    for txn in transactions:
        txn_id   = txn["transaction_id"]
        cust_id  = txn["customer_id"]
        location = txn["location"]

        cust_node  = f"CUST:{cust_id}"
        txn_node   = f"TXN:{txn_id}"
        loc_node   = f"LOC:{location}"

        # Customer node
        if not G.has_node(cust_node):
            G.add_node(cust_node, type="customer", label=cust_id,
                       customer_id=cust_id, risk_profile="unknown")

        # Transaction node
        txn_attrs = dict(
            type="transaction",
            label=txn_id,
            transaction_id=txn_id,
            customer_id=cust_id,
            amount=float(txn.get("amount", 0)),
            location=location,
            transaction_type=txn.get("transaction_type", ""),
            time=txn.get("time", ""),
            risk_level=None,
            risk_score=None,
            fraud_reasons=[],
        )
        # Overlay risk attributes from analysis if available
        if txn_id in result_map:
            r = result_map[txn_id]
            txn_attrs["risk_level"]   = r.get("risk_level")
            txn_attrs["risk_score"]   = r.get("risk_score")
            txn_attrs["fraud_reasons"] = r.get("fraud_reasons", [])

        G.add_node(txn_node, **txn_attrs)

        # Update customer risk_profile to worst risk level seen
        current_profile = G.nodes[cust_node]["risk_profile"]
        rl = txn_attrs["risk_level"]
        if rl == "High Risk" or (rl == "Suspicious" and current_profile != "High Risk"):
            G.nodes[cust_node]["risk_profile"] = rl
        elif current_profile == "unknown" and rl == "Safe":
            G.nodes[cust_node]["risk_profile"] = "Safe"

        # Location node
        if not G.has_node(loc_node):
            is_domestic = any(kw in location.lower() for kw in _DOMESTIC_KEYWORDS)
            G.add_node(
                loc_node,
                type="location",
                label=location,
                location=location,
                risk_score=_location_risk(location),
                is_domestic=is_domestic,
            )

        # Edges
        G.add_edge(cust_node, txn_node, type="MADE")
        G.add_edge(txn_node, loc_node, type="AT_LOCATION")

    # ── Pass 2: Add FOLLOWS edges (rapid succession) ─────────────────
    cust_txns: dict[str, list] = {}
    for txn in transactions:
        cust_txns.setdefault(txn["customer_id"], []).append(txn)

    for cust_id, txn_list in cust_txns.items():
        # Sort by parsed time
        try:
            sorted_txns = sorted(txn_list, key=lambda t: _parse_time(t["time"]))
        except Exception:
            continue

        for i in range(len(sorted_txns) - 1):
            t_a = sorted_txns[i]
            t_b = sorted_txns[i + 1]
            try:
                delta = abs(
                    (_parse_time(t_b["time"]) - _parse_time(t_a["time"])).total_seconds()
                )
                if delta <= config.RAPID_TXN_WINDOW_SEC:
                    G.add_edge(
                        f"TXN:{t_a['transaction_id']}",
                        f"TXN:{t_b['transaction_id']}",
                        type="FOLLOWS",
                        delta_seconds=round(delta, 1),
                    )
            except Exception:
                continue

    return G


def get_graph_stats(G: nx.DiGraph) -> dict:
    """Return aggregate statistics about the graph."""
    nodes_by_type: dict[str, int] = {"customer": 0, "transaction": 0, "location": 0}
    high_risk_count = 0
    for _, data in G.nodes(data=True):
        ntype = data.get("type", "unknown")
        nodes_by_type[ntype] = nodes_by_type.get(ntype, 0) + 1
        if data.get("risk_level") == "High Risk":
            high_risk_count += 1

    # Fraud clusters: weakly connected components in undirected view
    undirected = G.to_undirected()
    components = list(nx.connected_components(undirected))
    fraud_clusters = sum(
        1 for comp in components
        if any(
            G.nodes[n].get("risk_level") == "High Risk"
            for n in comp
            if G.has_node(n)
        )
    )

    # Top-5 nodes by degree centrality
    centrality = nx.degree_centrality(G)
    top5 = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_nodes":        G.number_of_nodes(),
        "total_edges":        G.number_of_edges(),
        "customer_nodes":     nodes_by_type.get("customer", 0),
        "transaction_nodes":  nodes_by_type.get("transaction", 0),
        "location_nodes":     nodes_by_type.get("location", 0),
        "high_risk_transactions": high_risk_count,
        "fraud_clusters":     fraud_clusters,
        "top5_by_centrality": [{"node": n, "centrality": round(c, 4)} for n, c in top5],
    }


def to_cypher_export(G: nx.DiGraph) -> str:
    """Generate Neo4j Cypher CREATE statements for the graph (no DB connection needed)."""
    lines = ["// Neo4j Cypher export — generated by core/graph.py", ""]

    # Nodes
    for node_id, data in G.nodes(data=True):
        ntype  = data.get("type", "node").capitalize()
        safe_id = node_id.replace(":", "_").replace(",", "").replace(" ", "_")
        props = {k: v for k, v in data.items() if k not in ("type",) and v is not None}
        prop_str = ", ".join(f'{k}: {_cypher_val(v)}' for k, v in props.items())
        lines.append(f"CREATE (n_{safe_id}:{ntype} {{{prop_str}}})")

    lines.append("")

    # Edges
    for src, dst, data in G.edges(data=True):
        rel_type = data.get("type", "RELATED").upper()
        safe_src = src.replace(":", "_").replace(",", "").replace(" ", "_")
        safe_dst = dst.replace(":", "_").replace(",", "").replace(" ", "_")
        edge_props = {k: v for k, v in data.items() if k != "type" and v is not None}
        if edge_props:
            prop_str = " {" + ", ".join(f'{k}: {_cypher_val(v)}' for k, v in edge_props.items()) + "}"
        else:
            prop_str = ""
        lines.append(f"CREATE (n_{safe_src})-[:{rel_type}{prop_str}]->(n_{safe_dst})")

    return "\n".join(lines)


def _cypher_val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        items = ", ".join(_cypher_val(i) for i in v)
        return f"[{items}]"
    return f'"{str(v)}"'
