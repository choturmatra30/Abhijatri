"""TikZ entity-relationship diagram for the SRS (crow's-foot notation), generated from the table list below.

Entities are drawn as boxes with the table name and key attributes; each relationship line carries crow's-foot
symbols at both ends (inner symbol = maximum, outer symbol = minimum) and a verb phrase. Columns and keys follow
backend/app/models.py. Coordinates are in millimetres; the layout is three columns wide for a portrait page.
"""

import math

W = 45.8           # box width (three columns fill the 166 mm portrait text width)
HEAD = 6.5         # header height
LINE = 4.0         # attribute line height
PAD = 2.2
GAP_X = 14.0
GAP_Y = 12.0
COLX = [0.0, W + GAP_X, 2 * (W + GAP_X)]
FILL = {"core": "erCore", "review": "erReview", "mod": "erMod", "note": "erNote"}

# name: (column, row, group, attributes); an attribute starting with "~" continues the line above (indented)
ENTITIES = {
    "user_roles": (0, 1, "core", ["PK id", "FK user_id", "role, revoked_at"]),
    "destinations": (1, 1, "core", ["PK id", "name_bn, name_en", "status"]),
    "destination_rating_stats": (2, 1, "core", ["PK, FK destination_id", "community_rating_sum,", "~community_rating_count",
                                                "guest_rating_sum, _count"]),
    "users": (0, 2, "core", ["PK id", "email, display_name", "status, last_visit_on"]),
    "reviews": (1, 2, "review", ["PK id", "FK destination_id", "FK author_user_id", "~(null for a guest)", "status, version",
                                 "visit_month", "overall_rating", "counted_rating", "FK current_revision_id"]),
    "review_receipts": (2, 2, "review", ["PK id", "FK review_id", "key_id, digest"]),
    "moderation_actions": (0, 3, "mod", ["PK id", "FK review_id", "FK actor_user_id", "decision, new_status"]),
    "review_revisions": (1, 3, "review", ["PK id", "FK review_id", "sequence, status", "title, body, rating"]),
    "review_media": (2, 3, "review", ["PK id", "FK review_id", "FK uploader_id", "kind, state"]),
    "appeals": (0, 4, "mod", ["PK id", "FK appellant_user_id", "~(null for a guest)", "FK moderation_action_id", "state, deadline_at"]),
    "review_category_ratings": (1, 4, "review", ["PK, FK revision_id", "PK category", "rating (1 to 5)"]),
    "moderation_tasks": (2, 4, "mod", ["PK id", "task_type, subject_id", "FK assigned_to", "status, lease_expires_at"]),
    "outbox_events": (0, 5, "note", ["PK id", "topic, aggregate_id", "status, attempts"]),
    "notifications": (1, 5, "note", ["PK id", "FK event_id", "FK recipient_user_id", "kind, priority"]),
    "notification_deliveries": (2, 5, "note", ["PK id", "FK notification_id", "channel, status", "attempt_count"]),
}


def _height(name):
    return HEAD + LINE * len(ENTITIES[name][3]) + PAD


def _row_tops():
    tops, y = {}, 0.0
    for r in sorted({v[1] for v in ENTITIES.values()}):
        tops[r] = y
        y -= max(_height(n) for n, v in ENTITIES.items() if v[1] == r) + GAP_Y
    return tops, y + GAP_Y


ROWTOP, BOTTOM = _row_tops()


def box(name):
    col, row, _, _ = ENTITIES[name]
    x0, top = COLX[col], ROWTOP[row]
    return x0, top - _height(name), x0 + W, top  # x0, y0, x1, y1


def mid_y(name):
    x0, y0, x1, y1 = box(name)
    return (y0 + y1) / 2


def cx(name):
    x0, _, x1, _ = box(name)
    return (x0 + x1) / 2


# Relationships: (parent, child, verb, parent-end cardinality, child-end cardinality, path from parent to child, label segment)
def relationships():
    b = box
    gap01 = W + GAP_X / 2
    gap12 = 2 * W + GAP_X * 1.5
    y1 = ROWTOP[1] - 10.0
    y2 = ROWTOP[2] - 10.0
    y5 = ROWTOP[5] - 10.0
    y_low = b("reviews")[1] + 6.0
    return [
        ("users", "user_roles", "has", "1", "0..N", [(cx("users"), b("users")[3]), (cx("users"), b("user_roles")[1])], 0),
        ("users", "reviews", "writes", "0..1", "0..N", [(b("users")[2], y2), (b("reviews")[0], y2)], 0),
        ("destinations", "reviews", "reviewed in", "1", "0..N",
         [(cx("destinations"), b("destinations")[1]), (cx("destinations"), b("reviews")[3])], 0),
        ("destinations", "destination_rating_stats", "has", "1", "0..1", [(b("destinations")[2], y1), (b("destination_rating_stats")[0], y1)], 0),
        ("reviews", "review_receipts", "proved by", "1", "0..N", [(b("reviews")[2], y2), (b("review_receipts")[0], y2)], 0),
        ("reviews", "review_media", "shows", "1", "0..N",
         [(b("reviews")[2], y_low), (gap12, y_low), (gap12, mid_y("review_media")), (b("review_media")[0], mid_y("review_media"))], 1),
        ("reviews", "review_revisions", "has", "1", "1..N", [(cx("reviews"), b("reviews")[1]), (cx("reviews"), b("review_revisions")[3])], 0),
        ("review_revisions", "review_category_ratings", "scores", "1", "0..N",
         [(cx("review_revisions"), b("review_revisions")[1]), (cx("review_revisions"), b("review_category_ratings")[3])], 0),
        ("reviews", "moderation_actions", "decided by", "1", "0..N",
         [(b("reviews")[0], y_low), (gap01, y_low), (gap01, mid_y("moderation_actions")), (b("moderation_actions")[2], mid_y("moderation_actions"))], 1),
        ("moderation_actions", "appeals", "appealed in", "0..1", "0..N",
         [(cx("moderation_actions"), b("moderation_actions")[1]), (cx("moderation_actions"), b("appeals")[3])], 0),
        ("outbox_events", "notifications", "becomes", "1", "0..N", [(b("outbox_events")[2], y5), (b("notifications")[0], y5)], 0),
        ("notifications", "notification_deliveries", "sent as", "0..1", "0..N",
         [(b("notifications")[2], y5), (b("notification_deliveries")[0], y5)], 0),
    ]


def _end(px, py, ux, uy, card):
    """Crow's-foot symbols at an end point (px, py); (ux, uy) points from the line into the entity."""
    vx, vy = -uy, ux
    out = []

    def p(d, s=0.0):
        return f"({px - ux * d + vx * s:.2f},{py - uy * d + vy * s:.2f})"

    many = card.endswith("N")
    minimum = card.split("..")[0] if ".." in card else "1"
    if many:  # fork: apex 3.4 mm out, toes on the entity edge
        out.append(rf"\draw[erline] {p(3.4)} -- {p(0, 2.0)};")
        out.append(rf"\draw[erline] {p(3.4)} -- {p(0, -2.0)};")
        out.append(rf"\draw[erline] {p(3.4)} -- {p(0)};")
        outer = 4.8
    else:  # inner bar for "one"
        out.append(rf"\draw[erline] {p(2.4, 2.0)} -- {p(2.4, -2.0)};")
        outer = 4.4
    if minimum == "0":
        cxp, cyp = px - ux * (outer + 1.2), py - uy * (outer + 1.2)
        out.append(rf"\draw[erline,fill=white] ({cxp:.2f},{cyp:.2f}) circle (1.2);")
    else:
        out.append(rf"\draw[erline] {p(outer, 2.0)} -- {p(outer, -2.0)};")
    return out


def _dir(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    return dx / ln, dy / ln


def _tex(s):
    return s.replace("_", r"\_")


def tikz() -> str:
    out = [r"\begin{tikzpicture}[x=1mm,y=1mm,erline/.style={line width=0.6pt,draw=erInk},"
           r"lbl/.style={font=\scriptsize\itshape,fill=white,inner sep=1pt,align=center,text=erInk}]"]
    for name, (_, _, grp, attrs) in ENTITIES.items():
        x0, y0, x1, y1 = box(name)
        out.append(rf"\fill[{FILL[grp]}] ({x0},{y1 - HEAD:.2f}) rectangle ({x1},{y1});")
        out.append(rf"\draw[line width=0.8pt,draw=erInk] ({x0},{y0:.2f}) rectangle ({x1},{y1});")
        out.append(rf"\draw[line width=0.5pt,draw=erInk] ({x0},{y1 - HEAD:.2f}) -- ({x1},{y1 - HEAD:.2f});")
        out.append(rf"\node[font=\footnotesize\sffamily\bfseries] at ({(x0 + x1) / 2:.2f},{y1 - HEAD / 2:.2f}) {{{_tex(name)}}};")
        for i, a in enumerate(attrs):
            y = y1 - HEAD - PAD / 2 - LINE * (i + 0.5)
            if a.startswith("~"):
                txt = r"\hspace*{3mm}" + _tex(a[1:])
            elif a.startswith("PK, FK "):
                txt = r"\textbf{PK, FK} " + _tex(a[7:])
            elif a.startswith(("PK ", "FK ")):
                txt = rf"\textbf{{{a[:2]}}} " + _tex(a[3:])
            else:
                txt = _tex(a)
            out.append(rf"\node[anchor=west,font=\footnotesize\sffamily] at ({x0 + 1.8},{y:.2f}) {{{txt}}};")
    for parent, child, verb, pc, cc, path, seg in relationships():
        out.append(r"\draw[erline] " + " -- ".join(f"({x:.2f},{y:.2f})" for x, y in path) + ";")
        ux, uy = _dir(path[1], path[0])
        out += _end(path[0][0], path[0][1], ux, uy, pc)
        ux, uy = _dir(path[-2], path[-1])
        out += _end(path[-1][0], path[-1][1], ux, uy, cc)
        a, b = path[seg], path[seg + 1]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        if abs(a[1] - b[1]) < 0.01 and abs(a[0] - b[0]) < 24:   # short horizontal: label above the line
            out.append(rf"\node[lbl,fill=none,anchor=south] at ({mx:.2f},{my + 2.3:.2f}) {{{verb}}};")
        elif abs(a[0] - b[0]) < 0.01 and abs(a[1] - b[1]) < 30:  # short vertical: label beside the line
            out.append(rf"\node[lbl,fill=none,anchor=west] at ({mx + 2.6:.2f},{my:.2f}) {{{verb}}};")
        else:
            out.append(rf"\node[lbl] at ({mx:.2f},{my:.2f}) {{{verb}}};")
    # legend: one row under the diagram
    ly = BOTTOM - 9.0
    out.append(rf"\node[anchor=west,font=\footnotesize\sffamily\bfseries] at (0,{ly}) {{Crow's-foot key:}};")
    for i, (card, text) in enumerate([("1", "exactly one"), ("0..1", "zero or one"), ("1..N", "one or many"), ("0..N", "zero or many")]):
        lx = 26 + i * 34.5
        out.append(rf"\draw[erline] ({lx},{ly}) -- ({lx + 12},{ly});")
        out.append(rf"\draw[line width=0.8pt,draw=erInk] ({lx + 12},{ly - 2.8}) -- ({lx + 12},{ly + 2.8});")
        out += _end(lx + 12, ly, 1.0, 0.0, card)
        out.append(rf"\node[anchor=west,font=\footnotesize\sffamily] at ({lx + 13.5},{ly}) {{{text}}};")
    out.append(r"\end{tikzpicture}")
    return "\n".join(out)


if __name__ == "__main__":
    print(tikz())
