"""Roll-ups of cost over hierarchies (cost-code tree, WBS tree) and cross-walks to client coding systems. Pure Decimal arithmetic.

Invariant (checked by callers and tests): the sum over roots of a roll-up + the 'unassigned' bucket equals the grand total - nothing is lost or double counted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

ZERO = Decimal(0)
UNASSIGNED = "(unassigned)"


@dataclass
class Node:
    code: str
    parent: str | None
    own: Decimal = ZERO
    total: Decimal = ZERO
    children: list[str] = field(default_factory=list)
    level: int = 1


def tree_rollup(values: dict[str, Decimal], parent: dict[str, str | None], names: dict[str, str] | None = None) -> dict:
    """values: amount booked directly on a node (key may be None/unknown -> '(unassigned)'). parent: node -> parent (None for roots).
    Returns {'nodes': {code: Node}, 'roots': [...], 'unassigned': Decimal, 'grand_total': Decimal}."""
    nodes = {c: Node(c, p) for c, p in parent.items()}
    for c, n in nodes.items():
        if n.parent in nodes:
            nodes[n.parent].children.append(c)
        else:
            n.parent = None if n.parent not in nodes else n.parent
    unassigned = ZERO
    for k, v in values.items():
        if v is None:
            continue
        if k in nodes:
            nodes[k].own += v
        else:
            unassigned += v
    # post-order accumulate (iterative; depth-safe)
    order: list[str] = []
    level: dict[str, int] = {}
    roots = sorted(c for c, n in nodes.items() if n.parent is None)
    stack = [(r, 1) for r in roots]
    while stack:
        c, lv = stack.pop()
        level[c] = lv
        order.append(c)
        for ch in sorted(nodes[c].children):
            stack.append((ch, lv + 1))
    for c in reversed(order):
        n = nodes[c]
        n.level = level[c]
        n.total = n.own + sum((nodes[ch].total for ch in n.children), ZERO)
    grand = sum((nodes[r].total for r in roots), ZERO) + unassigned
    return {"nodes": nodes, "roots": roots, "unassigned": unassigned, "grand_total": grand, "order": sorted(order, key=lambda c: (_path(nodes, c)))}


def _path(nodes: dict[str, Node], c: str) -> tuple:
    out = []
    while c is not None:
        out.append(c)
        c = nodes[c].parent
    return tuple(reversed(out))


def crosswalk(values: dict[str, Decimal], mappings: list[tuple[str, str]]) -> dict:
    """Allocate amounts booked on internal cost codes to client codes. mappings: (client_code, internal cost-code or prefix); the LONGEST matching prefix
    wins; if two different client codes tie on the longest prefix the amount is reported as 'ambiguous' (never split by guesswork).
    Returns {'by_client': {code: Decimal}, 'unmapped': {cost_code: Decimal}, 'ambiguous': {cost_code: [client codes]}, 'total_mapped', 'grand_total'}."""
    by_client: dict[str, Decimal] = {}
    unmapped: dict[str, Decimal] = {}
    ambiguous: dict[str, list[str]] = {}
    amb_total = ZERO
    for cc, v in sorted(values.items(), key=lambda kv: str(kv[0])):
        if v is None:
            continue
        key = cc or ""
        hits = [(len(pre), cl) for cl, pre in mappings if pre and key.startswith(pre)]
        if not hits:
            unmapped[cc or UNASSIGNED] = unmapped.get(cc or UNASSIGNED, ZERO) + v
            continue
        best = max(h[0] for h in hits)
        winners = sorted({cl for ln, cl in hits if ln == best})
        if len(winners) > 1:
            ambiguous[cc] = winners
            amb_total += v
            continue
        by_client[winners[0]] = by_client.get(winners[0], ZERO) + v
    mapped = sum(by_client.values(), ZERO)
    um = sum(unmapped.values(), ZERO)
    return {"by_client": by_client, "unmapped": unmapped, "ambiguous": ambiguous, "ambiguous_total": amb_total, "total_mapped": mapped,
            "grand_total": mapped + um + amb_total}


def matrix(cells: dict[tuple[str, str], Decimal]) -> dict:
    """Cross-tab {(row, col): amount} with row/column totals."""
    rows: dict[str, Decimal] = {}
    cols: dict[str, Decimal] = {}
    grand = ZERO
    for (r, c), v in cells.items():
        rows[r] = rows.get(r, ZERO) + v
        cols[c] = cols.get(c, ZERO) + v
        grand += v
    return {"cells": cells, "row_totals": rows, "col_totals": cols, "grand_total": grand}
