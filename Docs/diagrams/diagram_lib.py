"""Small drawing library for the Abhijatri documents (Gane-Sarson DFD, state, sequence, ERD, Venn).

One data structure per diagram; the same data feeds the picture, the rule checker and the Word tables,
so a diagram and its data dictionary cannot disagree. Run `python make_diagrams.py` to rebuild everything.
Colours are the Okabe-Ito colour-blind-safe palette; meaning never depends on colour alone (shape and text
also differ).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

INK = "#1b1b1b"
GREY = "#6b6b6b"
PAL = {
    "entity_fill": "#FFF1D6",   # orange tint
    "entity_edge": "#D55E00",
    "process_fill": "#ECECEC",  # neutral grey
    "process_edge": "#4D4D4D",
    "store_fill": "#E3F3EA",    # green tint
    "store_edge": "#009E73",
    "proto_fill": "#FFFFFF",
    "flow": "#333333",
    "accent": "#CC79A7",
    "yellow": "#F0E442",
    "sky": "#56B4E9",
    "vermillion": "#D55E00",
    "green": "#009E73",
    "blue": "#0072B2",
    "orange": "#E69F00",
    "purple": "#CC79A7",
}
plt.rcParams["font.family"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


# --------------------------------------------------------------------------------------- DFD model


@dataclass
class Node:
    id: str
    kind: str  # entity | process | store
    label: str
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
    proto: bool = False  # prototype / not available: drawn dashed and grey
    tag: str = ""        # text shown instead of the id (a duplicate data store shows the same D-number twice)
    dup: bool = False    # duplicate store marker (extra bar), Gane-Sarson convention
    loaded_by: str = ""  # a store filled from outside the system boundary (seed data); counts as its writer


@dataclass
class Flow:
    src: str
    dst: str
    label: str
    data: str = ""        # what the flow carries, for the data dictionary
    rad: float | None = None  # curvature of the arrow; None = choose automatically (straight unless it would cross a box)
    t: float = 0.5        # preferred label position along the arrow (0..1)
    dx: float = 0.0       # label nudge
    dy: float = 0.0
    both: bool = False    # read and write of a store drawn as one double-headed arrow
    off: float = 0.0      # shift sideways (drawn as parallel lines when a pair of opposite flows share two nodes)
    wrap: int = 22        # label wrap width in characters
    of: str = ""          # the parent-diagram flow this flow realises (defaults to its own label)


@dataclass
class DFD:
    key: str
    title: str
    level: str  # context | 0 | 1 | 2
    nodes: list[Node]
    flows: list[Flow]
    size: tuple[float, float] = (12.6, 8.6)  # inches; 1 data unit = 0.1 inch
    parent: str | None = None      # key of the parent (logical) diagram
    parent_process: str | None = None  # process id that this diagram decomposes
    note: str = ""
    yshift: float = 0.0  # added to every node's y (lets layouts be written bottom-up without clipping)
    note_bottom: bool = True  # draw the note at the bottom-left instead of under the title
    legend: tuple[float, float] | None = None  # legend origin in data units; default bottom right
    group: str = ""  # sheets of one logical diagram share a group key (the key used for balancing)
    sheet: str = ""  # e.g. "sheet 1 of 3"
    xscale: float = 1.0  # multiplies every node's x (stretches a layout written for a narrower sheet)
    _by_id: dict[str, Node] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        defaults = {"entity": (19.0, 7.0), "process": (22.0, 10.4), "store": (24.0, 5.4)}
        for n in self.nodes:
            dw, dh = defaults[n.kind]
            n.w = n.w or dw
            n.h = n.h or dh
            n.y += self.yshift
            n.x *= self.xscale
        self._by_id = {n.id: n for n in self.nodes}
        self.group = self.group or self.key

    def node(self, node_id: str) -> Node:
        return self._by_id[node_id]


def lanes(key: str, title: str, *, lanes: list[tuple], flows: list[Flow], size=(12.6, 9.4), **kw) -> DFD:
    """Lay out a sheet as horizontal lanes, one per process: the process in the middle, its people on the left and its
    stores and services on the right. A node used by several processes is drawn once per lane (a duplicate, marked
    with the Gane-Sarson duplicate stroke), so no flow has to cross another lane. Flows are written with plain ids;
    each end that has a copy in the other end's lane is pointed at that copy.

    lanes: [(process Node, [left (id, kind, label[, extra])], [right (id, kind, label[, extra])]), ...]
    """
    W, H = size[0] * 10, size[1] * 10
    top, bottom = H - 8.0, 15.0
    weights = [spec[3] if len(spec) > 3 else 1.0 for spec in lanes]
    unit = (top - bottom) / sum(weights)
    nodes: list[Node] = []
    copies: dict[tuple[str, str], str] = {}
    counts: dict[str, int] = {}
    for spec in lanes:
        for side in (spec[1], spec[2]):
            for item in side:
                counts[item[0]] = counts.get(item[0], 0) + 1

    def spread(k, lo, hi):
        if k == 1:
            return [(lo + hi) / 2]
        return [hi - i * (hi - lo) / (k - 1) for i in range(k)]

    edge = top
    for i, spec in enumerate(lanes):
        proc, left, right = spec[:3]
        band = unit * weights[i]
        yc = edge - band / 2
        edge -= band
        proc.x, proc.y = W * 0.47, yc
        proc.w, proc.h = 24.0, max(10.4, band - 6.5)  # tall enough that every flow in the lane is a straight horizontal line
        nodes.append(proc)
        pad = min(5.5, band / 4)
        for item, y in zip(left, spread(len(left), yc - band / 2 + pad, yc + band / 2 - pad)):
            nid, kind, label = item[:3]
            extra = item[3] if len(item) > 3 else {}
            cid = nid if counts[nid] == 1 else f"{nid}~{proc.id}"
            nodes.append(Node(cid, kind, label, 13, y, dup=counts[nid] > 1, **extra))
            copies[(nid, proc.id)] = cid
        k = len(right)
        two = k > max(2, int(band / 8.5))
        rp = max(pad, 5.4)
        ys = spread(k, yc - band / 2 + rp, yc + band / 2 - rp)
        for j, (item, y) in enumerate(zip(right, ys)):
            nid, kind, label = item[:3]
            extra = item[3] if len(item) > 3 else {}
            cid = nid if counts[nid] == 1 else f"{nid}~{proc.id}"
            x = (W - 33 if j % 2 == 0 else W - 13.5) if two else W - 20
            nodes.append(Node(cid, kind, label, x, y, dup=counts[nid] > 1, **extra))
            copies[(nid, proc.id)] = cid
    out = []
    for f in flows:
        if (f.dst, f.src) in copies:      # src is the process, dst an outside node
            f.dst = copies[(f.dst, f.src)]
        elif (f.src, f.dst) in copies:    # dst is the process
            f.src = copies[(f.src, f.dst)]
        out.append(f)
    return DFD(key=key, title=title, nodes=nodes, flows=out, size=size, **kw)


def merge_sheets(diagrams: list[DFD]) -> list[DFD]:
    """One logical diagram per group: the union of its sheets' nodes and flows (used by every check)."""
    out: dict[str, DFD] = {}
    for d in diagrams:
        if d.group not in out:
            out[d.group] = DFD(key=d.group, title=d.title.split(" (sheet")[0], level=d.level, nodes=[], flows=[], parent=d.parent,
                               parent_process=d.parent_process)
        m = out[d.group]
        for n in d.nodes:
            if n.id not in m._by_id:
                m.nodes.append(n)
                m._by_id[n.id] = n
        m.flows.extend(d.flows)
    return list(out.values())


def check_dfd(d: DFD) -> list[str]:
    """Structural rules (an empty list means the diagram obeys the Gane-Sarson rules)."""
    problems: list[str] = []
    ids = {n.id for n in d.nodes}
    inbound: dict[str, int] = {n.id: 0 for n in d.nodes}
    outbound: dict[str, int] = {n.id: 0 for n in d.nodes}
    seen: set[tuple[str, str, str]] = set()
    for f in d.flows:
        if f.src not in ids or f.dst not in ids:
            problems.append(f"{d.key}: flow '{f.label}' has an unknown end ({f.src} -> {f.dst})")
            continue
        a, b = d.node(f.src).kind, d.node(f.dst).kind
        if not f.label.strip():
            problems.append(f"{d.key}: unnamed flow {f.src} -> {f.dst}")
        if "process" not in (a, b):
            problems.append(f"{d.key}: flow '{f.label}' joins two non-processes ({a} -> {b}); every flow needs a process")
        key = (f.src, f.dst, f.label)
        if key in seen:
            problems.append(f"{d.key}: duplicate flow {key}")
        seen.add(key)
        outbound[f.src] += 1
        inbound[f.dst] += 1
        if f.both:
            outbound[f.dst] += 1
            inbound[f.src] += 1
    for n in d.nodes:
        if n.kind == "process" and (inbound[n.id] == 0 or outbound[n.id] == 0):
            problems.append(f"{d.key}: process {n.id} has no {'input' if inbound[n.id] == 0 else 'output'} (black hole or miracle)")
        if n.kind in ("entity", "store") and inbound[n.id] + outbound[n.id] == 0:
            problems.append(f"{d.key}: {n.kind} {n.id} is not connected")
    return problems


def canon(node_id: str) -> str:
    """A drawn copy is the same node: "Guest~4.1" is Guest, and a duplicate store D4b is D4."""
    node_id = node_id.split("~")[0]
    return node_id[:-1] if node_id.endswith('b') and node_id[:-1].startswith('D') and node_id[:-1][1:].isdigit() else node_id


def check_stores(logical: list[DFD]) -> list[str]:
    """Rule 9: every data store is written by some process and read by some process, across all diagrams."""
    writes: dict[str, int] = {}
    reads: dict[str, int] = {}
    loaded: set[str] = set()
    stores: set[str] = set()
    for d in logical:
        for n in d.nodes:
            if n.kind == "store":
                stores.add(canon(n.id))
                if n.loaded_by:
                    loaded.add(canon(n.id))
        for f in d.flows:
            s, t = d.node(f.src), d.node(f.dst)
            if t.kind == "store":
                writes[canon(t.id)] = writes.get(canon(t.id), 0) + 1
                if f.both:
                    reads[canon(t.id)] = reads.get(canon(t.id), 0) + 1
            if s.kind == "store":
                reads[canon(s.id)] = reads.get(canon(s.id), 0) + 1
                if f.both:
                    writes[canon(s.id)] = writes.get(canon(s.id), 0) + 1
    problems = []
    for s in sorted(stores):
        if not writes.get(s) and s not in loaded:
            problems.append(f"store {s} is never written (rule 9)")
        if not reads.get(s):
            problems.append(f"store {s} is never read (rule 9)")
    return problems


def boundary(d: DFD, pids: set[str]) -> dict[tuple[str, str], set[str]]:
    """(outside node, 'in'|'out') -> set of parent-flow names realised, seen from a set of processes."""
    sig: dict[tuple[str, str], set[str]] = {}
    for f in d.flows:
        name = f.of or f.label
        if f.src in pids and f.dst not in pids:
            sig.setdefault((canon(f.dst), "out"), set()).add(name)
            if f.both:
                sig.setdefault((canon(f.dst), "in"), set()).add(name)
        if f.dst in pids and f.src not in pids:
            sig.setdefault((canon(f.src), "in"), set()).add(name)
            if f.both:
                sig.setdefault((canon(f.src), "out"), set()).add(name)
    return sig


def own_boundary(d: DFD, pids: set[str]) -> dict[tuple[str, str], set[str]]:
    """Like boundary(), but with each flow's own label (what the parent shows)."""
    sig: dict[tuple[str, str], set[str]] = {}
    for f in d.flows:
        if f.src in pids and f.dst not in pids:
            sig.setdefault((canon(f.dst), "out"), set()).add(f.label)
            if f.both:
                sig.setdefault((canon(f.dst), "in"), set()).add(f.label)
        if f.dst in pids and f.src not in pids:
            sig.setdefault((canon(f.src), "in"), set()).add(f.label)
            if f.both:
                sig.setdefault((canon(f.src), "out"), set()).add(f.label)
    return sig


def check_balance(logical: list[DFD]) -> list[str]:
    """Content balancing: every child boundary flow realises a named flow of the parent process on the same node and
    direction, and every such parent flow is realised by at least one child flow. Local stores are allowed."""
    by_key = {d.key: d for d in logical}
    problems = []
    for child in logical:
        if not child.parent:
            continue
        parent = by_key[child.parent]
        pids = {"0"} if parent.level == "context" else {child.parent_process}
        psig = own_boundary(parent, pids)
        own = {n.id for n in child.nodes if n.kind == "process"}
        csig = boundary(child, own)
        parent_nodes = {canon(n.id) for n in parent.nodes}
        for (node, direction), names in csig.items():
            if node not in parent_nodes:
                kinds = {x.kind for x in child.nodes if canon(x.id) == node}
                if kinds != {"store"}:
                    problems.append(f"{child.key}: {node} is not on the parent diagram and is not a local store")
                users = {f.src if f.dst in own else f.dst for f in child.flows if canon(f.src) == node or canon(f.dst) == node}
                continue
            for name in names:
                if name not in psig.get((node, direction), set()):
                    problems.append(f"{child.key}: flow '{name}' ({direction} {node}) does not realise any flow of {parent.key}/{','.join(sorted(pids))}")
        for (node, direction), names in psig.items():
            for name in names:
                if name not in csig.get((node, direction), set()):
                    problems.append(f"{child.key}: parent flow '{name}' ({direction} {node}) is not realised by any child flow")
    return problems


# --------------------------------------------------------------------------------------- DFD drawing


def _exit_point(n: Node, p: tuple[float, float], d: tuple[float, float]) -> tuple[float, float]:
    """Where a ray from p (inside node n) travelling along d leaves the node's rectangle."""
    hw, hh = n.w / 2, n.h / 2
    best = math.inf
    if d[0] > 1e-9:
        best = min(best, (n.x + hw - p[0]) / d[0])
    elif d[0] < -1e-9:
        best = min(best, (n.x - hw - p[0]) / d[0])
    if d[1] > 1e-9:
        best = min(best, (n.y + hh - p[1]) / d[1])
    elif d[1] < -1e-9:
        best = min(best, (n.y - hh - p[1]) / d[1])
    if best is math.inf or best < 0:
        best = 0.0
    return p[0] + d[0] * best, p[1] + d[1] * best


def _flow_ends(a: Node, b: Node, off: float, rad: float, gap: float = 0.35):
    """End points on the two boxes. For a curved arrow the ends leave along the curve's tangent.
    A small box beside a tall one (or above a wide one) is joined by a straight horizontal (vertical) line."""
    ax_, ay_, bx_, by_ = a.x, a.y, b.x, b.y
    if not rad:
        big, small = (a, b) if a.h >= b.h else (b, a)
        if abs(a.x - b.x) > (a.w + b.w) / 2 and big.h > small.h * 1.8 and big.y - big.h / 2 + 2 <= small.y <= big.y + big.h / 2 - 2:
            ay_ = by_ = small.y
        big, small = (a, b) if a.w >= b.w else (b, a)
        if abs(a.y - b.y) > (a.h + b.h) / 2 and big.w > small.w * 1.8 and big.x - big.w / 2 + 2 <= small.x <= big.x + big.w / 2 - 2:
            ax_ = bx_ = small.x
    a = Node(a.id, a.kind, a.label, ax_, ay_, a.w, a.h)
    b = Node(b.id, b.kind, b.label, bx_, by_, b.w, b.h)
    dx, dy = b.x - a.x, b.y - a.y
    ln = math.hypot(dx, dy) or 1.0
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    pa = (a.x + nx * off, a.y + ny * off)
    pb = (b.x + nx * off, b.y + ny * off)
    if rad:
        cx, cy = _bezier_mid(pa, pb, rad)
        da = (cx - pa[0], cy - pa[1])
        db = (cx - pb[0], cy - pb[1])
        la, lb = math.hypot(*da) or 1.0, math.hypot(*db) or 1.0
        da, db = (da[0] / la, da[1] / la), (db[0] / lb, db[1] / lb)
    else:
        da, db = (ux, uy), (-ux, -uy)
    p1 = _exit_point(a, pa, da)
    p2 = _exit_point(b, pb, db)
    return (p1[0] + da[0] * gap, p1[1] + da[1] * gap), (p2[0] + db[0] * gap, p2[1] + db[1] * gap)


def _bezier_mid(p1, p2, rad):
    (x1, y1), (x2, y2) = p1, p2
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    cx, cy = mx + rad * dy, my - rad * dx
    return cx, cy


def _bezier_point(p1, p2, rad, t):
    cx, cy = _bezier_mid(p1, p2, rad)
    x = (1 - t) ** 2 * p1[0] + 2 * (1 - t) * t * cx + t**2 * p2[0]
    y = (1 - t) ** 2 * p1[1] + 2 * (1 - t) * t * cy + t**2 * p2[1]
    return x, y


def _bezier_normal(p1, p2, rad, t):
    """Unit normal of the curve at t (left of the travel direction)."""
    a = _bezier_point(p1, p2, rad, max(0.0, t - 0.01))
    b = _bezier_point(p1, p2, rad, min(1.0, t + 0.01))
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    return -dy / ln, dx / ln


def _wrap(text: str, width: int) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def _rect(n: Node, pad: float = 0.0):
    return (n.x - n.w / 2 - pad, n.y - n.h / 2 - pad, n.x + n.w / 2 + pad, n.y + n.h / 2 + pad)


def _inside(p, r) -> bool:
    return r[0] <= p[0] <= r[2] and r[1] <= p[1] <= r[3]


def _overlap(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _path(p1, p2, rad, n=80):
    return [_bezier_point(p1, p2, rad, i / n) for i in range(n + 1)]


LABEL_FONT = 11.0
NODE_FONT = 12.0


def draw_dfd(d: DFD, path: str, *, dpi: int = 200) -> list[str]:
    """Draw one sheet. Returns layout problems: an arrow passing under a box it does not join, a label touching a box,
    two labels touching, or a label sitting on another flow's arrow."""
    problems: list[str] = []
    fw, fh = d.size
    fig = plt.figure(figsize=(fw, fh))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fw * 10)
    ax.set_ylim(0, fh * 10)
    ax.set_aspect("equal")
    ax.axis("off")
    renderer = fig.canvas.get_renderer()

    def bbox_of(artist, pad=0.0):
        bb = artist.get_window_extent(renderer).transformed(ax.transData.inverted())
        return (bb.x0 - pad, bb.y0 - pad, bb.x1 + pad, bb.y1 + pad)

    title = d.title + (f" ({d.sheet})" if d.sheet else "")
    t_art = ax.text(2, fh * 10 - 2.2, title, fontsize=16, fontweight="bold", color=INK, va="top")
    reserved = [bbox_of(t_art, 0.4)]
    if d.note:
        n_art = ax.text(2, 1.6 if d.note_bottom else fh * 10 - 6.0, _wrap(d.note, int(fw * 7.0)), fontsize=10.0, color=GREY,
                        va="bottom" if d.note_bottom else "top")
        reserved.append(bbox_of(n_art, 0.4))

    # nodes
    for n in d.nodes:
        dashed = "--" if n.proto else "-"
        if n.kind == "entity":
            ax.add_patch(Rectangle((n.x - n.w / 2, n.y - n.h / 2), n.w, n.h, fc=PAL["proto_fill"] if n.proto else PAL["entity_fill"],
                                   ec=PAL["entity_edge"], lw=1.8, ls=dashed, zorder=3))
            ax.add_patch(Rectangle((n.x - n.w / 2 + 0.5, n.y - n.h / 2 + 0.5), n.w - 1.0, n.h - 1.0, fc="none",
                                   ec=PAL["entity_edge"], lw=0.7, ls=dashed, zorder=3))
            ax.text(n.x, n.y, _wrap(n.label, 18), ha="center", va="center", fontsize=NODE_FONT, fontweight="bold", color=INK, zorder=4)
            if n.dup:  # duplicate marker: a diagonal stroke across the lower-right corner, Gane-Sarson convention
                x1, y0 = n.x + n.w / 2, n.y - n.h / 2
                ax.plot([x1 - 2.4, x1], [y0, y0 + 2.4], color=PAL["entity_edge"], lw=1.3, zorder=4)
        elif n.kind == "process":
            ax.add_patch(FancyBboxPatch((n.x - n.w / 2, n.y - n.h / 2), n.w, n.h, boxstyle="round,pad=0,rounding_size=1.4",
                                        fc=PAL["proto_fill"] if n.proto else PAL["process_fill"], ec=PAL["process_edge"], lw=1.8,
                                        ls=dashed, zorder=3))
            ax.plot([n.x - n.w / 2, n.x + n.w / 2], [n.y + n.h / 2 - 2.5, n.y + n.h / 2 - 2.5], color=PAL["process_edge"], lw=1.0,
                    ls=dashed, zorder=4)
            ax.text(n.x, n.y + n.h / 2 - 1.25, n.id, ha="center", va="center", fontsize=NODE_FONT, fontweight="bold", color=PAL["process_edge"], zorder=5)
            ax.text(n.x, n.y - 1.2, _wrap(n.label, 20), ha="center", va="center", fontsize=NODE_FONT, fontweight="bold", color=INK, zorder=5)
        else:  # store: open-ended rectangle with an id box
            x0, x1, y0, y1 = n.x - n.w / 2, n.x + n.w / 2, n.y - n.h / 2, n.y + n.h / 2
            ax.add_patch(Rectangle((x0, y0), n.w, n.h, fc=PAL["proto_fill"] if n.proto else PAL["store_fill"], ec="none", zorder=2))
            ax.plot([x0, x1], [y1, y1], color=PAL["store_edge"], lw=1.8, ls=dashed, zorder=3)
            ax.plot([x0, x1], [y0, y0], color=PAL["store_edge"], lw=1.8, ls=dashed, zorder=3)
            ax.plot([x0, x0], [y0, y1], color=PAL["store_edge"], lw=1.8, ls=dashed, zorder=3)
            ax.plot([x0 + 4.6, x0 + 4.6], [y0, y1], color=PAL["store_edge"], lw=1.0, zorder=3)
            ax.text(x0 + 2.3, n.y, n.tag or canon(n.id), ha="center", va="center", fontsize=NODE_FONT, fontweight="bold", color=PAL["store_edge"], zorder=5)
            if n.dup:  # duplicate marker: a second bar on the right end
                ax.plot([x1 - 1.2, x1 - 1.2], [y0, y1], color=PAL["store_edge"], lw=1.0, zorder=3)
            ax.text(x0 + 4.6 + (n.w - 4.6) / 2, n.y, _wrap(n.label, 22), ha="center", va="center", fontsize=NODE_FONT - 0.6, color=INK, zorder=5)

    rects = {n.id: _rect(n) for n in d.nodes}
    lx, ly = d.legend if d.legend else (fw * 10 - 51, 6.0)
    leg_box = (lx - 0.5, ly - 4.2, lx + 50, ly + 1.6)
    blockers = dict(rects)
    blockers["(legend)"] = leg_box
    for k, r in enumerate(reserved):
        blockers[f"(title or note {k})"] = r

    # a pair of opposite flows between the same two nodes is drawn as two parallel arrows
    pairs = {(f.src, f.dst) for f in d.flows if not f.both}

    # route every flow: straight if it clears every other box, else the gentlest curve that does
    routes = []
    for f in d.flows:
        a, b = d.node(f.src), d.node(f.dst)
        off = f.off
        if off == 0.0 and not f.both and (f.dst, f.src) in pairs:
            off = 1.6
        candidates = [f.rad] if f.rad is not None else [0.0, 0.1, -0.1, 0.18, -0.18, 0.26, -0.26, 0.35, -0.35, 0.45, -0.45]
        chosen = None
        for rad in candidates:
            p1, p2 = _flow_ends(a, b, off, rad)
            pts = _path(p1, p2, rad)
            hits = [nid for nid, r in blockers.items() if nid not in (f.src, f.dst) and any(_inside(p, (r[0] - 0.6, r[1] - 0.6, r[2] + 0.6, r[3] + 0.6)) for p in pts)]
            if not hits:
                chosen = (rad, p1, p2, pts)
                break
            if chosen is None:
                chosen = (rad, p1, p2, pts, hits)
        if len(chosen) == 5:
            problems.append(f"{d.key}: flow '{f.label}' ({f.src} -> {f.dst}) passes under {chosen[4]}")
            chosen = chosen[:4]
        routes.append((f,) + chosen)

    for f, rad, p1, p2, pts in routes:
        style = "<|-|>" if f.both else "-|>"
        ax.add_patch(FancyArrowPatch(p1, p2, connectionstyle=f"arc3,rad={rad}", arrowstyle=style, mutation_scale=15, lw=1.3,
                                     color=PAL["flow"], zorder=1, shrinkA=0, shrinkB=0))

    # place labels: try positions along the arrow and beside it; keep the one that touches nothing
    placed: list[tuple] = []
    node_boxes = [(nid, (r[0] - 0.3, r[1] - 0.3, r[2] + 0.3, r[3] + 0.3)) for nid, r in rects.items()]
    W, H = fw * 10, fh * 10
    for i, (f, rad, p1, p2, pts) in enumerate(routes):
        text = ax.text(0, 0, _wrap(f.label, f.wrap), ha="center", va="center", fontsize=LABEL_FONT, color=INK, zorder=6,
                       bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="none", alpha=0.95))
        ts = [f.t] + [t for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.35, 0.65, 0.25, 0.75, 0.2, 0.8, 0.45, 0.55, 0.15, 0.85, 0.12, 0.88, 0.1, 0.9) if abs(t - f.t) > 1e-6]
        best = None
        for t in ts:
            bx, by = _bezier_point(p1, p2, rad, t)
            nx, ny = _bezier_normal(p1, p2, rad, t)
            for side in (0.0, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0):
                x, y = bx + f.dx + nx * side * 1.9, by + f.dy + ny * side * 1.9
                text.set_position((x, y))
                bb = bbox_of(text, 0.15)
                score = 0
                if bb[0] < 0.5 or bb[2] > W - 0.5 or bb[1] < 0.5 or bb[3] > H - 0.5:
                    score += 1000
                if any(_overlap(bb, r) for r in reserved) or _overlap(bb, leg_box):
                    score += 1000
                for nid, r in node_boxes:
                    if _overlap(bb, r):
                        score += 500
                for other in placed:
                    if _overlap(bb, other[1]):
                        score += 500
                for j, (g, _, _, _, gpts) in enumerate(routes):
                    if j != i and any(_inside(p, bb) for p in gpts):
                        score += 40
                score += abs(side) * 2 + abs(t - f.t) * 4
                if best is None or score < best[0]:
                    best = (score, (x, y), bb)
                if score < 5:
                    break
            if best and best[0] < 5:
                break
        text.set_position(best[1])
        placed.append((f, best[2]))
        if best[0] >= 500:
            problems.append(f"{d.key}: label '{f.label}' touches a box or another label")
        elif best[0] >= 40:
            problems.append(f"{d.key}: label '{f.label}' sits on another arrow")

    # legend
    ax.add_patch(Rectangle((lx, ly - 1.1), 3.6, 2.2, fc=PAL["entity_fill"], ec=PAL["entity_edge"], lw=1.3))
    ax.text(lx + 4.6, ly, "External entity", fontsize=9.5, va="center")
    ax.add_patch(FancyBboxPatch((lx + 19, ly - 1.1), 3.6, 2.2, boxstyle="round,pad=0,rounding_size=0.6", fc=PAL["process_fill"], ec=PAL["process_edge"], lw=1.3))
    ax.text(lx + 23.6, ly, "Process", fontsize=9.5, va="center")
    has_store = any(n.kind == "store" for n in d.nodes)
    if has_store:
        ax.plot([lx + 33, lx + 33], [ly - 1.1, ly + 1.1], color=PAL["store_edge"], lw=1.3)
        ax.plot([lx + 33, lx + 36.6], [ly + 1.1, ly + 1.1], color=PAL["store_edge"], lw=1.3)
        ax.plot([lx + 33, lx + 36.6], [ly - 1.1, ly - 1.1], color=PAL["store_edge"], lw=1.3)
        ax.text(lx + 37.6, ly, "Data store", fontsize=9.5, va="center")
    if any(n.proto for n in d.nodes):
        ax.plot([lx, lx + 3.6], [ly - 3.0, ly - 3.0], color=GREY, lw=1.3, ls="--")
        ax.text(lx + 4.6, ly - 3.0, "Dashed = prototype, not available yet", fontsize=9.5, va="center")
    for nid, r in node_boxes:
        if _overlap(leg_box, r):
            problems.append(f"{d.key}: legend overlaps {nid}")
    for nid, r in node_boxes:
        if any(_overlap(r, q) for q in reserved):
            problems.append(f"{d.key}: {nid} overlaps the title or note")
    for r in reserved:
        if _overlap(leg_box, r):
            problems.append(f"{d.key}: legend overlaps the title or note")
    for f, bb in placed:
        if _overlap(leg_box, bb):
            problems.append(f"{d.key}: legend overlaps label '{f.label}'")

    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return problems


# --------------------------------------------------------------------------------------- shared label placement


def _setup(size, title, subtitle=""):
    fw, fh = size
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fw * 10)
    ax.set_ylim(0, fh * 10)
    ax.set_aspect("equal")
    ax.axis("off")
    renderer = fig.canvas.get_renderer()

    def bbox_of(artist, pad=0.0):
        bb = artist.get_window_extent(renderer).transformed(ax.transData.inverted())
        return (bb.x0 - pad, bb.y0 - pad, bb.x1 + pad, bb.y1 + pad)

    reserved = []
    t = ax.text(2, fh * 10 - 2.2, title, fontsize=16, fontweight="bold", color=INK, va="top")
    reserved.append(bbox_of(t, 0.4))
    if subtitle:
        s = ax.text(2, reserved[0][1] - 1.2, _wrap(subtitle, int(fw * 12)), fontsize=10.5, color=GREY, va="top")
        reserved.append(bbox_of(s, 0.4))
    return fig, ax, bbox_of, reserved


def _place(text, bbox_of, candidates, hard, placed, paths, W, H, own=None):
    """Put a text artist at the best of the candidate points. Returns (score, bbox)."""
    best = None
    for k, (x, y, cost) in enumerate(candidates):
        text.set_position((x, y))
        bb = bbox_of(text, 0.15)
        score = cost
        if bb[0] < 0.3 or bb[2] > W - 0.3 or bb[1] < 0.3 or bb[3] > H - 0.3:
            score += 1000
        score += 500 * sum(1 for r in hard if _overlap(bb, r))
        score += 500 * sum(1 for r in placed if _overlap(bb, r))
        score += 40 * sum(1 for j, pts in enumerate(paths) if j != own and any(_inside(p, bb) for p in pts))
        if best is None or score < best[0]:
            best = (score, (x, y), bb)
        if score < 3:
            break
    text.set_position(best[1])
    return best[0], best[2]


# --------------------------------------------------------------------------------------- state diagram


def draw_states(path: str, title: str, states: dict, edges: list[tuple], size=(14.4, 9.4), dpi=200, dashed=frozenset(),
                note: str = "", start=None, group=None) -> list[str]:
    """states: id -> (x, y, fill); edges: (src, dst, label). Routing and label places are computed; returns layout problems.
    group: optional (x0, y0, x1, y1, label) composite state; an edge from "__group" leaves its border (UML superstate)."""
    fig, ax, bbox_of, reserved = _setup(size, title)
    W, H = size[0] * 10, size[1] * 10
    BW, BH = 22.0, 7.4
    problems: list[str] = []
    nodes = {k: Node(k, "process", k, v[0], v[1], BW, BH) for k, v in states.items()}
    if start:
        nodes["__start"] = Node("__start", "process", "", start[0], start[1], 2.4, 2.4)
        ax.add_patch(Circle(start, 1.2, fc=INK, ec=INK, zorder=4))
    if group:
        gx0, gy0, gx1, gy1, glabel = group
        ax.add_patch(FancyBboxPatch((gx0, gy0), gx1 - gx0, gy1 - gy0, boxstyle="round,pad=0,rounding_size=3.0", fc="#FAFAFA", ec=GREY,
                                    lw=1.4, ls=(0, (6, 3)), zorder=1))
        ax.text(gx0 + 1.5, gy1 - 1.2, glabel, ha="left", va="top", fontsize=10.5, fontweight="bold", color=GREY, zorder=2)
        nodes["__group"] = Node("__group", "process", "", (gx0 + gx1) / 2, (gy0 + gy1) / 2, gx1 - gx0, gy1 - gy0)
    for k, (x, y, col) in states.items():
        ax.add_patch(FancyBboxPatch((x - BW / 2, y - BH / 2), BW, BH, boxstyle="round,pad=0,rounding_size=2.0", fc=col, ec=INK, lw=1.6,
                                    ls="--" if k in dashed else "-", zorder=3))
        ax.text(x, y, k.replace("_", "_\n") if len(k) > 13 else k, ha="center", va="center", fontsize=11, fontweight="bold", zorder=4)
    if note:
        n_art = ax.text(2, 1.6, _wrap(note, int(size[0] * 11)), fontsize=10, color=GREY, va="bottom")
        reserved.append(bbox_of(n_art, 0.4))
    rects = {k: _rect(n) for k, n in nodes.items() if k != "__group"}
    pairs = {(e[0], e[1]) for e in edges}
    routes = []
    for s, t, label in edges:
        a, b = nodes[s], nodes[t]
        cands = [0.28] if (t, s) in pairs else [0.0, 0.15, -0.15, 0.3, -0.3, 0.45, -0.45]
        chosen = None
        for rad in cands:
            p1, p2 = _flow_ends(a, b, 0.0, rad, gap=0.4)
            pts = _path(p1, p2, rad)
            hits = [k for k, r in rects.items() if k not in (s, t) and any(_inside(p, (r[0] - 0.8, r[1] - 0.8, r[2] + 0.8, r[3] + 0.8)) for p in pts)]
            if not hits:
                chosen = (rad, p1, p2, pts)
                break
            chosen = chosen or (rad, p1, p2, pts, hits)
        if len(chosen) == 5:
            problems.append(f"state edge {s} -> {t} passes under {chosen[4]}")
            chosen = chosen[:4]
        routes.append((label,) + chosen)
    for label, rad, p1, p2, pts in routes:
        ax.add_patch(FancyArrowPatch(p1, p2, connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>", mutation_scale=16, lw=1.4,
                                     color=PAL["flow"], zorder=2, shrinkA=0, shrinkB=0))
    placed = []
    paths = [r[4] for r in routes]
    hard = list(rects.values()) + reserved
    for i, (label, rad, p1, p2, pts) in enumerate(routes):
        if not label:
            continue
        txt = ax.text(0, 0, _wrap(label, 22), ha="center", va="center", fontsize=10, zorder=6,
                      bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.95))
        cands = []
        for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.25, 0.75, 0.2, 0.8):
            bx, by = _bezier_point(p1, p2, rad, t)
            nx_, ny_ = _bezier_normal(p1, p2, rad, t)
            for side in (0.0, 1.0, -1.0):
                cands.append((bx + nx_ * side * 3.5, by + ny_ * side * 3.5, abs(t - 0.5) * 4 + abs(side) * 6))
        score, bb = _place(txt, bbox_of, cands, hard, placed, paths, W, H, own=i)
        placed.append(bb)
        if score >= 500:
            problems.append(f"state label '{label}' touches a box or another label")
        elif score >= 40:
            problems.append(f"state label '{label}' sits on another arrow")
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return problems


# --------------------------------------------------------------------------------------- sequence diagram


def draw_sequence(path: str, title: str, actors: list[str], messages: list[tuple], size=(14.4, 11.0), dpi=200, note: str = "",
                  fs: float = 10.0, colours: list[tuple[str, str]] | None = None, call_colour: str | None = None,
                  return_colour: str | None = None, self_colour: str | None = None, tight: bool = False) -> list[str]:
    """messages: (from, to, text[, kind]) with kind 'call' | 'return' | 'self'. Returns layout problems.
    fs is the label font size; colours gives a (fill, edge) pair per participant; calls, replies and self-calls can each
    have their own arrow colour."""
    fig, ax, bbox_of, reserved = _setup(size, title)
    W, H = size[0] * 10, size[1] * 10
    n = len(actors)
    cw = 0.074 * fs  # average character width in drawing units at this font size
    span = (W - 8.0) / n
    box_w = min(22.0, span * 0.92)
    left, right = 4.0 + span / 2, W - 4.0 - span / 2
    xs = [left + i * (right - left) / (n - 1) for i in range(n)]
    top = reserved[-1][1] - 6.0 if title else H - 9.0 * fs / 10.0 / 2 - 2.0
    bottom = 9.0 if note else 4.0
    call_c, ret_c, self_c = call_colour or PAL["flow"], return_colour or PAL["flow"], self_colour or PAL["flow"]
    head_h = 9.0 * fs / 10.0
    for i, (x, name) in enumerate(zip(xs, actors)):
        fill, edge = colours[i] if colours else (PAL["process_fill"], PAL["process_edge"])
        ax.add_patch(FancyBboxPatch((x - box_w / 2, top - head_h / 2), box_w, head_h, boxstyle="round,pad=0,rounding_size=1.2", fc=fill,
                                    ec=edge, lw=1.8, zorder=3))
        ax.text(x, top, _wrap(name, max(8, int(box_w / (cw * 1.4)))), ha="center", va="center", fontsize=fs + 0.5, fontweight="bold",
                zorder=4, linespacing=1.1)
        ax.plot([x, x], [top - head_h / 2, bottom], color=edge, lw=1.3, ls=(0, (4, 3)), zorder=1, alpha=0.75)
    rows = sum(1.5 if (m[3] if len(m) > 3 else "call") == "self" else 1.0 for m in messages)
    step = (top - head_h / 2 - bottom - 3.0) / (rows + 0.3)
    y = top - head_h / 2 - step * 1.0
    boxes: list[tuple] = []
    problems = []
    for i, m in enumerate(messages):
        a, b, text = m[0], m[1], m[2]
        kind = m[3] if len(m) > 3 else "call"
        if kind == "self":
            h = step * 0.7
            ax.add_patch(FancyArrowPatch((xs[a] + 0.2, y), (xs[a] + 0.2, y - h), connectionstyle="arc3,rad=-1.4", arrowstyle="-|>",
                                         mutation_scale=14, lw=1.6, color=self_c, zorder=2))
            last = a == n - 1
            room = (xs[a] - 4.0) if last else (W - xs[a] - 8.0)
            t = ax.text(xs[a] + (-2.0 if last else 5.0), y - h / 2, _wrap(text, max(14, int(room / cw))), ha="right" if last else "left",
                        va="center", fontsize=fs, zorder=6, color=INK,
                        bbox=dict(boxstyle="round,pad=0.18", fc="#F6F0FA", ec=self_c, lw=0.6, alpha=0.97))
            dy = step * 1.6
        else:
            col = ret_c if kind == "return" else call_c
            ax.add_patch(FancyArrowPatch((xs[a], y), (xs[b], y), arrowstyle="-|>", mutation_scale=14, lw=1.6, color=col,
                                         ls=(0, (5, 3)) if kind == "return" else "-", zorder=2, shrinkA=0, shrinkB=0))
            t = ax.text((xs[a] + xs[b]) / 2, y + 0.6, _wrap(text, max(14, int(max(abs(xs[a] - xs[b]), span * 1.85) / cw * 0.95))), ha="center", va="bottom",
                        fontsize=fs, zorder=6, color=INK, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.95))
            dy = step
        bb = bbox_of(t, 0.1)
        if any(_overlap(bb, o) for o in boxes):
            problems.append(f"sequence label {i + 1} overlaps another label")
        boxes.append(bb)
        ax.text(1.8, y - (step * 0.35 if kind == "self" else 0), str(i + 1), fontsize=fs - 1, color=GREY, va="center", ha="center")
        y -= dy
    if note:
        ax.text(2, 1.6, _wrap(note, int(W / cw)), fontsize=fs - 0.5, color=GREY, va="bottom")
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    if tight:
        _trim(path, dpi)
    return problems


# --------------------------------------------------------------------------------------- ERD (crow's foot)


def _end_marker(ax, p, q, spec):
    """Crow's-foot marker at end p of the line p->q. spec: '1', '0..1', '1..N' or '0..N'."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    ln = math.hypot(dx, dy) or 1.0
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    kw = dict(color=INK, lw=1.3, zorder=5)
    many = spec.endswith("N")
    if many:  # three prongs meeting 2.6 units from the box
        tip = (p[0] + ux * 2.6, p[1] + uy * 2.6)
        for s in (-1.3, 0.0, 1.3):
            ax.plot([tip[0], p[0] + nx * s], [tip[1], p[1] + ny * s], **kw)
    bar = 3.4 if many else 1.6
    ax.plot([p[0] + ux * bar + nx * 1.3, p[0] + ux * bar - nx * 1.3], [p[1] + uy * bar + ny * 1.3, p[1] + uy * bar - ny * 1.3], **kw)
    if spec == "1":
        b2 = 2.6
        ax.plot([p[0] + ux * b2 + nx * 1.3, p[0] + ux * b2 - nx * 1.3], [p[1] + uy * b2 + ny * 1.3, p[1] + uy * b2 - ny * 1.3], **kw)
    if spec.startswith("0"):
        c = bar + 1.6
        ax.add_patch(Circle((p[0] + ux * c, p[1] + uy * c), 0.9, fc="white", ec=INK, lw=1.3, zorder=6))


def draw_erd(path: str, title: str, entities: dict, rels: list[tuple], size=(14.4, 12.0), dpi=200, note: str = "") -> list[str]:
    """entities: name -> (x, y, [field lines], colour); rels: (a, b, label, end_a, end_b). Returns layout problems."""
    fig, ax, bbox_of, reserved = _setup(size, title)
    W, H = size[0] * 10, size[1] * 10
    BW = 25.0
    boxes = {}
    for name, (x, y, fields, col) in entities.items():
        h = 4.2 + 2.3 * len(fields) + 1.0
        boxes[name] = Node(name, "process", name, x, y, BW, h)
        ax.add_patch(Rectangle((x - BW / 2, y - h / 2), BW, h, fc="white", ec=INK, lw=1.4, zorder=3))
        ax.add_patch(Rectangle((x - BW / 2, y + h / 2 - 3.8), BW, 3.8, fc=col, ec=INK, lw=1.4, zorder=4))
        ax.text(x, y + h / 2 - 1.9, name, ha="center", va="center", fontsize=10, fontweight="bold", zorder=5)
        for i, line in enumerate(fields):
            ax.text(x - BW / 2 + 0.9, y + h / 2 - 5.2 - 2.3 * i, line, ha="left", va="center", fontsize=9, zorder=5, color=INK)
    if note:
        n_art = ax.text(2, 1.4, _wrap(note, int(size[0] * 11)), fontsize=10, color=GREY, va="bottom")
        reserved.append(bbox_of(n_art, 0.4))
    rects = {k: _rect(n) for k, n in boxes.items()}
    problems, routes = [], []
    for k, r in rects.items():
        if any(_overlap(r, q) for q in reserved):
            problems.append(f"ERD box {k} overlaps the title or note")
    for a, b, label, ea, eb in rels:
        na, nb = boxes[a], boxes[b]
        chosen = None
        for rad in (0.0, 0.15, -0.15, 0.3, -0.3):
            p1, p2 = _flow_ends(na, nb, 0.0, rad, gap=0.0)
            pts = _path(p1, p2, rad)
            hits = [k for k, r in rects.items() if k not in (a, b) and any(_inside(p, (r[0] - 0.6, r[1] - 0.6, r[2] + 0.6, r[3] + 0.6)) for p in pts)]
            if not hits:
                chosen = (rad, p1, p2, pts)
                break
            chosen = chosen or (rad, p1, p2, pts, hits)
        if len(chosen) == 5:
            problems.append(f"ERD line {a} - {b} passes under {chosen[4]}")
            chosen = chosen[:4]
        rad, p1, p2, pts = chosen
        ax.add_patch(FancyArrowPatch(p1, p2, connectionstyle=f"arc3,rad={rad}", arrowstyle="-", lw=1.3, color=PAL["flow"], zorder=2))
        q1 = _bezier_point(p1, p2, rad, 0.08)
        q2 = _bezier_point(p1, p2, rad, 0.92)
        _end_marker(ax, p1, q1, ea)
        _end_marker(ax, p2, q2, eb)
        routes.append((label, rad, p1, p2, pts))
    placed = []
    hard = list(rects.values()) + reserved
    paths = [r[4] for r in routes]
    for i, (label, rad, p1, p2, pts) in enumerate(routes):
        txt = ax.text(0, 0, label, fontsize=9.5, ha="center", va="center", color=GREY, zorder=6, style="italic",
                      bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.95))
        cands = [(*_bezier_point(p1, p2, rad, t), abs(t - 0.5) * 4) for t in (0.5, 0.4, 0.6, 0.32, 0.68)]
        score, bb = _place(txt, bbox_of, cands, hard, placed, paths, W, H, own=i)
        placed.append(bb)
        if score >= 500:
            problems.append(f"ERD label '{label}' touches a box or another label")
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return problems


# --------------------------------------------------------------------------------------- Venn (three sets)


def draw_venn3(path: str, title: str, circles: list[dict], regions: dict, size=(12.0, 10.4), dpi=200, subtitle: str = "",
               name_size: float = 12, tight: bool = False, names_vertical: bool = False) -> list[str]:
    """circles: three dicts with x, y, r, colour, name. regions: membership key ('A', 'AB', 'ABC', ...) -> (text, size, weight).
    Each region's text is centred on the point of that region farthest from every circle edge, so a label can only sit in
    its own region; the check reports any label that still crosses an edge."""
    fig, ax, bbox_of, reserved = _setup(size, title, subtitle)
    W, H = size[0] * 10, size[1] * 10
    for c in circles:
        ax.add_patch(Circle((c["x"], c["y"]), c["r"], fc=c["colour"], alpha=0.22, ec="none", zorder=2))
        ax.add_patch(Circle((c["x"], c["y"]), c["r"], fc="none", ec=c["colour"], lw=2.6, zorder=3))
    names = "ABC"

    def member(px, py):
        return "".join(n for n, c in zip(names, circles) if math.hypot(px - c["x"], py - c["y"]) < c["r"])

    def edge_dist(px, py):
        return min(abs(math.hypot(px - c["x"], py - c["y"]) - c["r"]) for c in circles)

    best: dict[str, tuple[float, float, float]] = {}
    x0 = min(c["x"] - c["r"] for c in circles)
    x1 = max(c["x"] + c["r"] for c in circles)
    y0 = min(c["y"] - c["r"] for c in circles)
    y1 = max(c["y"] + c["r"] for c in circles)
    steps = 160
    for i in range(steps + 1):
        for j in range(steps + 1):
            px, py = x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * j / steps
            m = member(px, py)
            if not m:
                continue
            d = edge_dist(px, py)
            if m not in best or d > best[m][2]:
                best[m] = (px, py, d)
    problems = []
    for key, (text, fs, weight) in regions.items():
        if key not in best:
            problems.append(f"Venn region {key} does not exist")
            continue
        px, py, _ = best[key]
        t = ax.text(px, py, text, ha="center", va="center", fontsize=fs, fontweight=weight, color=INK, zorder=7, linespacing=1.2)
        bb = bbox_of(t, 0.0)
        corners = [(bb[0], bb[1]), (bb[0], bb[3]), (bb[2], bb[1]), (bb[2], bb[3]), ((bb[0] + bb[2]) / 2, bb[1]), ((bb[0] + bb[2]) / 2, bb[3])]
        if any(member(*p) != key for p in corners):
            problems.append(f"Venn label for region {key} crosses a circle edge")
    cx = sum(c["x"] for c in circles) / 3
    cy = sum(c["y"] for c in circles) / 3
    for c in circles:  # set name outside its circle, on the line from the middle through the circle's centre
        dx, dy = c["x"] - cx, c["y"] - cy
        if names_vertical:  # straight above a top circle or below a bottom one: keeps the figure narrow
            dx, dy = 0.0, (1.0 if dy >= 0 else -1.0)
        ln = math.hypot(dx, dy) or 1.0
        nx_, ny_ = c["x"] + dx / ln * (c["r"] + 4.0), c["y"] + dy / ln * (c["r"] + 4.0)
        t = ax.text(nx_, ny_, c["name"], ha="center", va="center", fontsize=name_size, fontweight="bold", color=INK, zorder=7)
        bb = bbox_of(t, 0.3)
        for _ in range(40):  # push a wide name outward until none of its corners is inside its own circle
            if all(math.hypot(px - c["x"], py - c["y"]) > c["r"] + 0.8 for px in (bb[0], bb[2]) for py in (bb[1], bb[3])):
                break
            nx_, ny_ = nx_ + dx / ln * 0.8, ny_ + dy / ln * 0.8
            t.set_position((nx_, ny_))
            bb = bbox_of(t, 0.3)
        if any(_overlap(bb, r) for r in reserved):
            problems.append(f"Venn set name '{c['name']}' touches the title")
        if bb[0] < 0 or bb[2] > W or bb[1] < 0 or bb[3] > H:
            problems.append(f"Venn set name '{c['name']}' is off the page")
    if tight:  # no in-figure title: the document caption names the figure, so crop to the drawing
        fig.savefig(path, dpi=dpi, facecolor="white", bbox_inches="tight", pad_inches=0.12)
        from PIL import Image, ImageChops  # trim the white margin left by the empty title area
        im = Image.open(path).convert("RGB")
        box = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
        if box:
            m = int(0.12 * dpi)
            im.crop((max(box[0] - m, 0), max(box[1] - m, 0), min(box[2] + m, im.width), min(box[3] + m, im.height))).save(path)
    else:
        fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return problems


def _trim(path: str, dpi: int) -> None:
    """Crop the white margin around a saved figure (used when the document caption replaces the in-figure title)."""
    from PIL import Image, ImageChops
    im = Image.open(path).convert("RGB")
    box = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
    if box:
        m = int(0.12 * dpi)
        im.crop((max(box[0] - m, 0), max(box[1] - m, 0), min(box[2] + m, im.width), min(box[3] + m, im.height))).save(path)


# --------------------------------------------------------------------------------------- use case diagram


def _stick(ax, x, y, name, scale=1.0):
    s = scale
    ax.add_patch(Circle((x, y + 4.6 * s), 1.3 * s, fc="white", ec=INK, lw=1.4, zorder=4))
    ax.plot([x, x], [y + 3.3 * s, y + 0.2 * s], color=INK, lw=1.4, zorder=4)
    ax.plot([x - 2.0 * s, x + 2.0 * s], [y + 2.4 * s, y + 2.4 * s], color=INK, lw=1.4, zorder=4)
    ax.plot([x, x - 1.6 * s], [y + 0.2 * s, y - 2.4 * s], color=INK, lw=1.4, zorder=4)
    ax.plot([x, x + 1.6 * s], [y + 0.2 * s, y - 2.4 * s], color=INK, lw=1.4, zorder=4)
    ax.text(x, y - 3.6 * s, _wrap(name, 12), ha="center", va="top", fontsize=11, fontweight="bold", zorder=4)


def draw_usecases(path: str, title: str, actors: dict, cases: list[tuple], links: list[tuple], generalisations: list[tuple],
                  boundary: tuple, size=(10.0, 13.6), dpi=200, note: str = "") -> list[str]:
    """actors: id -> (x, y, name). cases: (id, x, y, text, status) with status built | prototype | planned.
    links: (actor, case). generalisations: (child actor, parent actor). boundary: (x0, y0, x1, y1, name)."""
    fig, ax, bbox_of, reserved = _setup(size, title)
    W, H = size[0] * 10, size[1] * 10
    bx0, by0, bx1, by1, bname = boundary
    ax.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fc="none", ec=INK, lw=1.6, zorder=1))
    ax.text((bx0 + bx1) / 2, by1 - 1.4, bname, ha="center", va="top", fontsize=12, fontweight="bold", zorder=2)
    EW, EH = 27.0, 6.6
    pos = {}
    style = {"built": (PAL["process_fill"], "-", ""), "prototype": (PAL["proto_fill"], "--", " (prototype)"), "planned": ("white", ":", " (not built)")}
    for cid, x, y, text, status in cases:
        fc, ls, suffix = style[status]
        ax.add_patch(Ellipse((x, y), EW, EH, fc=fc, ec=PAL["process_edge"], lw=1.5, ls=ls, zorder=3))
        ax.text(x, y, _wrap(text + suffix, 26), ha="center", va="center", fontsize=10, zorder=4, linespacing=1.1)
        pos[cid] = (x, y)
    for aid, (x, y, name) in actors.items():
        _stick(ax, x, y, name)
    problems = []
    for aid, cid in links:
        ax_, ay_ = actors[aid][0], actors[aid][1] + 1.5
        cx, cy = pos[cid]
        side = -1 if cx > ax_ else 1  # join the ellipse at the vertex that faces the actor
        ex, ey = cx + side * EW / 2, cy
        sx = ax_ + (2.6 if ex > ax_ else -2.6)
        ax.plot([sx, ex], [ay_, ey], color=GREY, lw=1.0, zorder=2)
        for ocid, ox, oy, _, _ in cases:
            if ocid == cid:
                continue
            for k in range(1, 40):
                px, py = sx + (ex - sx) * k / 40, ay_ + (ey - ay_) * k / 40
                if ((px - ox) / (EW / 2 + 0.4)) ** 2 + ((py - oy) / (EH / 2 + 0.4)) ** 2 < 1.0:
                    problems.append(f"use case line {aid} - {cid} crosses {ocid}")
                    break
    for child, parent in generalisations:
        (x1, y1, _), (x2, y2, _) = actors[child], actors[parent]
        ax.add_patch(FancyArrowPatch((x1, y1 + 7.0), (x2, y2 - 6.5), arrowstyle="-|>,head_length=1.0,head_width=0.6", mutation_scale=12,
                                     lw=1.3, color=INK, fc="white", zorder=3))
    lx, ly = bx0, by0 - 3.0
    for k, (status, label) in enumerate((("built", "Built and tested"), ("prototype", "Prototype screen only"), ("planned", "Not built"))):
        fc, ls, _ = style[status]
        ax.add_patch(Ellipse((lx + 3.5 + k * 24, ly), 6.0, 2.8, fc=fc, ec=PAL["process_edge"], lw=1.3, ls=ls))
        ax.text(lx + 7.5 + k * 24, ly, label, fontsize=9.5, va="center")
    if note:
        ax.text(2, 1.4, _wrap(note, int(size[0] * 11)), fontsize=10, color=GREY, va="bottom")
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return problems
