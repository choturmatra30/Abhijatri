"""Builds Docs/internal/Abhijatri-DFD-Drawing-Guide.docx: the team's how-to guide for drawing DFDs by hand.

This material used to be Parts A and B of Abhijatri-DFD.docx. It was moved out so that the submitted DFD document
contains only the model (review issue D35). Nothing here is submission content.
"""

from pathlib import Path

from docx_helpers import Doc

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "internal" / "Abhijatri-DFD-Drawing-Guide.docx"


def main() -> None:
    doc = Doc(
        "Drawing data flow diagrams",
        "Internal team guide: symbols, rules, levelling, procedure and tools (not for submission)",
        [
            ("Project", "Abhijatri (Team ChoturMatra, CSE 3102)"),
            ("Document", "Internal guide; the submitted model is Docs/Abhijatri-DFD.docx"),
            ("Version", "1.1, 31 October 2026 (moved out of the DFD document)"),
        ],
        "Abhijatri: DFD drawing guide (internal)",
    )
    doc.contents()
    # ------------------------------------------------------------------ Part A
    doc.h1("1. How to draw a data flow diagram")
    doc.h2("1.1 The four symbols (Gane-Sarson)")
    doc.table(
        ["Symbol", "Shape", "Meaning", "Naming rule", "Abhijatri example"],
        [
            ["External entity", "Rectangle with a double border", "A person or system outside the one you are modelling. It is a source or a sink of data.", "Noun", "Guest, Moderator, Supabase Auth"],
            ["Process", "Rounded rectangle with a number box", "Something that changes data: it must turn inputs into outputs.", "Verb + object, numbered 1.0, 4.3, 4.3.2", "4.0 Submit and manage reviews"],
            ["Data store", "Open-ended rectangle with a D-number", "Data at rest: a table, file or queue.", "Noun (what is kept), D1, D2 ...", "D3 Reviews"],
            ["Data flow", "Arrow with a label", "Data moving between the symbols above.", "Noun phrase (what data)", "guest review, receipt, scope secret"],
        ],
        [2.6, 2.8, 4.4, 3.2, 3.5], caption="DFD symbols",
    )
    doc.p("Yourdon-DeMarco notation uses circles for processes and two parallel lines for data stores. The meaning is identical. "
          "Use one notation throughout a document; this one uses Gane-Sarson because it is the style most university courses and tools (Visio, Lucidchart) provide.")
    doc.h2("1.2 The rules every DFD must follow")
    doc.table(
        ["#", "Rule", "Why it matters", "Common mistake"],
        [
            ["1", "Every process has at least one input and at least one output.", "A process with no input is a miracle (it invents data); with no output it is a black hole.", "A process that only receives data and never gives anything back"],
            ["2", "Data never flows directly between two external entities, two data stores, or an entity and a store. A process is always in between.", "Only processes can read, change and write data.", "An arrow from a database straight to a user"],
            ["3", "Name processes with a verb and an object, stores with a noun, flows with a noun phrase.", "Names make the diagram readable without a legend.", "\"Process data\", \"Send\" on an arrow, \"Database\" as a store name"],
            ["4", "Number processes (1.0, 4.3, 4.3.2) and stores (D1, D2).", "Numbers connect each level to its parent and to the data dictionary.", "Renumbering a process on a lower level"],
            ["5", "Balance the levels: the flows crossing the boundary of a child diagram equal the flows of the parent process it explains.", "Otherwise the levels describe different systems.", "Adding a new external flow while decomposing"],
            ["6", "Show data, not control. No decisions, loops, start or end symbols, and no timing.", "That belongs in a flowchart or sequence diagram.", "Drawing \"if approved\" diamonds"],
            ["7", "Keep 7 plus or minus 2 processes on one diagram.", "More than nine becomes unreadable; decompose instead.", "A single sheet with 20 processes"],
            ["8", "Use the same name and number for a store or entity everywhere it appears. A store used by two distant processes may be drawn twice with a duplicate marker.", "Prevents two copies being mistaken for two stores.", "Calling the same table \"Reviews\" on one page and \"Posts\" on another"],
            ["9", "Do not draw a store that nothing writes to or nothing reads from.", "An unused store is a design error or a missing process.", "A store with only outgoing arrows"],
            ["10", "A store that only one process uses may first appear on that process's child diagram (a local store).", "Keeps the parent diagram simple.", "Showing every internal table on level 0"],
            ["11", "Draw a request and its response as two arrows, and read-and-write of a store as one double-headed arrow.", "Keeps each flow's content clear.", "One arrow labelled \"login\" with no return"],
        ],
        [0.8, 5.0, 5.0, 5.7], caption="DFD rules", size=8.6,
    )
    doc.h2("1.3 Levelling: from one box to the detail")
    doc.bullets([
        "**Context diagram (level C).** The whole system is one process, numbered 0, surrounded by every external entity. No stores. It fixes the boundary of the system.",
        "**Level 0.** Open the box: 7 plus or minus 2 main processes, the data stores they share, and the same external entities with the same flows as the context diagram.",
        "**Level 1.** Take one level 0 process and open it into its own sub-processes (4.1, 4.2, ...). Its boundary flows must equal that process's flows at level 0.",
        "**Level 2.** Do the same again for a sub-process that is still too complex (4.3.1, 4.3.2, ...). Stop when a process can be described in a few sentences or one function.",
    ])
    doc.h2("1.4 Step-by-step procedure")
    doc.steps([
        "**Fix the boundary.** Write one sentence saying what is inside the system and what is not. (Abhijatri: the PWA, API, staff app and ops app; not Supabase, Cloudflare or the email provider.)",
        "**List the external entities.** Ask: who gives data to the system, and who receives data from it? Include other systems, not only people.",
        "**List the data stores.** Take the data model (tables, files, queues) and group tables that are always used together into one store. Write the table names beside each store.",
        "**List the events or use cases.** Each use case (\"submit review\", \"decide appeal\") suggests a process. Group closely related use cases into one level 0 process.",
        "**Draw the context diagram.** One process, all entities, a pair of arrows per entity (in and out). Name each arrow by the data it carries.",
        "**Draw level 0.** Place entities at the edge, processes in the middle, stores near the processes that use them. Put things that talk to each other next to each other to avoid crossing lines.",
        "**Label every flow** with the data, not the action: \"guest review, receipt\" not \"send review\".",
        "**Check the rules** in section 1.2 one by one, using the checklist in section 1.5.",
        "**Decompose** the processes that are too big or too important to leave as one box. Repeat steps 6 to 8 for each; keep numbering.",
        "**Balance and describe.** Compare each child's boundary flows with its parent's. Write the data dictionary: what each flow and store contains.",
        "**Walk through a scenario.** Trace one real case (a guest submits a review, a moderator publishes it) through the diagrams and confirm each step has an arrow.",
    ])
    doc.h2("1.5 Quick self-check before you submit")
    doc.table(
        ["Check", "Yes / No"],
        [[c, ""] for c in [
            "Every process has an input and an output",
            "No arrow joins two entities, two stores, or an entity and a store",
            "All flows are named with nouns; all processes with verb + object",
            "Processes and stores are numbered, and numbers match the data dictionary",
            "The level 0 entity flows match the context diagram",
            "Each child diagram's boundary flows match its parent process",
            "No decisions, loops or timing appear",
            "No more than nine processes on any diagram",
            "Prototype or planned parts are marked, not drawn as working",
            "A real scenario can be traced from start to finish",
            "Text is readable at A4 size (at least 8 pt after scaling)",
        ]],
        [13.5, 3.0], caption="Self-check list",
    )

    # ------------------------------------------------------------------ Part B
    doc.page_break()
    doc.h1("2. Tools for drawing DFDs by hand")
    doc.p("You do not need special software. Pick one tool the whole team can open and keep the editable source file in the repository next to the exported image.")
    doc.table(
        ["Tool", "Cost", "Best for", "Strengths", "Limits"],
        [
            ["diagrams.net (draw.io)", "Free; browser or desktop; saves .drawio to a file, Google Drive or GitHub", "Recommended for the team", "No account needed, exports PNG/SVG/PDF, rounded shapes, grid and snapping, runs offline in the desktop app", "No built-in DFD checker; you apply the rules yourself"],
            ["Lucidchart", "Free tier with limits on objects and documents", "Teams already using it (the use case diagram was drawn there)", "Shape libraries including data flow shapes (enable them from the Shape Libraries panel), real-time collaboration", "Free tier limits; export needs care"],
            ["Microsoft Visio", "Paid (Microsoft 365 plans), often available through a university", "Formal documents", "A data flow diagram template exists; precise alignment", "Heavy; Windows or web"],
            ["Visual Paradigm (Online or desktop)", "Free community tier with limits; paid for more", "Analysis diagrams with levelled decomposition", "DFD support and tools for linking levels", "Free edition limits and watermark on some exports"],
            ["PowerPoint or Google Slides", "Free or already installed", "Quick diagrams, presentations", "Everyone has it; Merge Shapes and alignment tools", "No connectors that stick as reliably; easy to mis-align"],
            ["Excalidraw or FigJam", "Free", "Sketching and brainstorming", "Fast, hand-drawn look, shareable link", "Not precise; fine for drafts, weaker for the final figure"],
            ["Mermaid (text) in GitHub or mermaid.live", "Free", "Diagrams that live in Markdown and update with the code", "Text source can be reviewed in a pull request; renders on GitHub", "No Gane-Sarson shapes; layout is automatic and can be hard to control"],
            ["PlantUML", "Free (needs Java or an online server)", "Developers who want text-defined diagrams", "Text source, many diagram types", "No native DFD symbols; approximate with rectangles and databases"],
            ["Python with matplotlib (how the figures here were made)", "Free", "Regenerating many diagrams from one data file and checking the rules automatically", "Rules checked by code; every figure rebuilt in one command", "Needs programming; layout coordinates are set by hand"],
            ["Pen and paper, then scan", "Free", "First draft on a whiteboard or in a meeting", "Fastest way to agree the structure", "Redraw digitally for submission"],
        ],
        [3.3, 3.0, 3.1, 4.1, 3.0], caption="Tools for drawing DFDs", size=8.4,
    )
    doc.h2("2.1 Recommended workflow for the team")
    doc.steps([
        "Agree the processes, stores and entities on paper or a whiteboard first (45 minutes). Photograph it.",
        "One person redraws it in diagrams.net using the steps in 2.2, and saves the **.drawio source** in `Docs/diagrams/`.",
        "Export a **PNG at 300 dpi (width at least 2400 px)** and an SVG. Insert the PNG into Word or LaTeX at the full text width.",
        "A second person checks the diagram against the self-check list (section 1.5) and the balancing table in the DFD document.",
        "Commit the source and the image together so the next edit starts from the source, not from the picture.",
    ])
    doc.h2("2.2 Drawing a DFD in diagrams.net (draw.io), step by step")
    doc.steps([
        "Open app.diagrams.net, choose **Create New Diagram**, a blank diagram, and save it first (the file is your source).",
        "Turn on **View > Grid** and **Snap to grid** so boxes align.",
        "**Process:** from the General shapes drag a *Rounded Rectangle*, about 4 cm by 2 cm. Type the number on the first line (4.0) and the name below. Draw a thin horizontal line under the number to make the number box.",
        "**External entity:** drag a *Rectangle*; add an inner rectangle slightly smaller to give the double border used here. Fill a pale orange.",
        "**Data store:** drag a *Rectangle*, then remove its right border (Edit Style: add `strokeColor=none` for the right edge by drawing the left, top and bottom lines only, or use the \"Data Store\" shape if your library has one). Put the D-number in a small box at the left.",
        "**Flows:** hover over a shape and drag from the blue arrow to the target shape so the connector sticks. Double-click the line to type the label. Use *Waypoints > Curved* only when you must avoid another box.",
        "For a **request and response** pair, draw two connectors and drag each slightly apart so they run parallel.",
        "Use **Format Panel > Arrange > Align** and **Distribute** to line up columns of processes.",
        "**Export:** File > Export as > PNG, set **Zoom 200 percent or DPI 300**, tick *Transparent background* off, *Border width 10*. Also export SVG.",
        "Save, and keep the .drawio next to the image in the repository.",
    ])
    doc.h2("2.3 Drawing a DFD in PowerPoint or Google Slides")
    doc.steps([
        "Use a **blank slide, widescreen (16:9)**. Turn on gridlines and guides (View).",
        "Insert **Shapes > Rounded Rectangle** for processes, **Rectangle** for entities, and a rectangle with only left, top and bottom outlines for stores (draw three lines, group them).",
        "Draw flows with **Insert > Shapes > Arrow** or **Elbow Connector**. Connectors snap to shape handles, so move shapes, not lines.",
        "Add labels as **text boxes** with a white fill so lines do not run through the words.",
        "Select everything, **Group**, then **File > Export (or Save as picture) as PNG** at the highest quality.",
    ])
    doc.h2("2.4 Drawing a DFD in Lucidchart or Visio")
    doc.bullets([
        "Create a new document, open **Shape Libraries**, search for \"data flow\" and enable the library. Choose the Gane-Sarson set so the shapes match this document.",
        "Drag process, entity and store shapes onto the page, then connect them with line tools; labels are attached to the lines so they move with them.",
        "Use **Align and Distribute** to keep columns tidy; use **Layers** if you want prototype parts on a separate, switchable layer.",
        "Export as PNG or PDF at print resolution.",
    ])
    doc.h2("2.5 Using Mermaid when you want the diagram to live in Markdown")
    doc.p("Mermaid has no Gane-Sarson shapes, but a flowchart can approximate a DFD: round brackets for processes, square brackets for entities, and cylinder shapes for stores. "
          "Use it for quick diagrams in a README, not for the final submission figure.")
    doc.code("""flowchart LR
    G[Guest] -->|guest review, receipt| P4(4.0 Submit and manage reviews)
    P4 -->|review id, status| G
    P4 <-->|reviews, revisions| D3[(D3 Reviews)]
    P4 -->|moderation task| D5[(D5 Moderation records)]""")
    doc.h2("2.6 Layout tips that make a DFD readable")
    doc.bullets([
        "Put **people on the left and outside systems on the right**; processes in the middle; stores near the processes that use them.",
        "Draw a **request and its response as two parallel arrows**, not one arrow with two heads, unless it is reading and writing a store.",
        "Put each flow's label **near the process end** of the arrow when several arrows leave the same entity; the lines are far apart there.",
        "Keep **crossings to a minimum**: move boxes, not lines. If one flow must cross others, make it a gentle curve and keep it short.",
        "Use **colour only as a helper** (orange entities, blue processes, green stores). Shapes and text must still make sense in black and white.",
        "Mark **prototype or planned** items with a dashed outline and say so in a note.",
    ])

    OUT.parent.mkdir(exist_ok=True)
    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
