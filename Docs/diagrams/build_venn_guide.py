"""Builds Docs/internal/Abhijatri-Venn-Drawing-Guide.docx: how to draw Venn diagrams by hand (internal team guide).

This was section 5 of Abhijatri-Venn-Diagram.docx; it was moved out so the submitted document holds only the diagrams (review issue V10).
"""

from pathlib import Path

from docx_helpers import Doc

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "internal" / "Abhijatri-Venn-Drawing-Guide.docx"
TIKZ = (HERE / "venn-tikz-example.tex").read_text(encoding="utf-8")
# the real environment (with options); the comment at the top of the file also mentions the word tikzpicture (review issue V9)
START = TIKZ.index("\\begin{tikzpicture}[")
BODY = TIKZ[START:TIKZ.index("\\end{tikzpicture}", START) + len("\\end{tikzpicture}")]


def main() -> None:
    doc = Doc(
        "Drawing Venn diagrams",
        "Internal team guide: planning, tools, step-by-step instructions and a tested TikZ snippet (not for submission)",
        [
            ("Project", "Abhijatri (Team ChoturMatra, CSE 3102)"),
            ("Document", "Internal guide; the submitted diagrams are in Docs/Abhijatri-Venn-Diagram.docx"),
            ("Version", "1.1, 31 October 2026 (moved out of the Venn document)"),
        ],
        "Abhijatri: Venn drawing guide (internal)",
    )
    doc.contents()
    doc.h1("1. How to draw a Venn diagram yourself")
    doc.h2("1.1 Plan it on paper first")
    doc.steps([
        "**Choose the sets.** Two or three is best. Four needs ellipses and is hard to read; five or more should be a table instead.",
        "**Name each set with a noun phrase** that a stranger understands (\"Community trust\", not \"Feature B\").",
        "**Write one short phrase for every region**: each set alone, each pair, and the centre. If a region is empty, say so or change the sets; an empty region is a useful finding.",
        "**Check every phrase is true** and that prototype or planned parts are marked.",
        "**Decide the size.** Use equal circles unless sizes carry meaning (then say so in a note, because readers will assume bigger means more).",
    ])
    doc.h2("1.2 Tools, and how to draw it in each")
    doc.table(
        ["Tool", "Cost", "Best for", "How (short)"],
        [
            ["diagrams.net (draw.io)", "Free", "Recommended: precise, editable, exports PNG and SVG", "Section 1.3"],
            ["PowerPoint or Google Slides", "Free or installed", "Quick and familiar", "Section 1.4"],
            ["Canva", "Free tier", "Polished look, templates", "Search \"Venn diagram\" in Templates; edit text; download PNG at high quality"],
            ["Lucidchart", "Free tier", "Team collaboration", "Use the \"Venn diagram\" template; drag circles, set transparency in the Fill panel"],
            ["Figma or FigJam", "Free", "Designers; styles and reuse", "Draw three ellipses, set Fill opacity to 30 percent, group, export PNG at 2x or 3x"],
            ["Inkscape", "Free", "Vector control, print quality", "Ellipse tool, set the alpha of the fill, use Path > Intersection to get the overlap shapes"],
            ["LaTeX with TikZ", "Free", "Matches the proposal (it already uses TikZ)", "Section 1.5; a tested snippet is given"],
            ["Python with matplotlib or matplotlib-venn", "Free", "Reproducible figures from code", "Section 1.6"],
            ["Pen, compass and paper", "Free", "First sketch with the team", "Draw circles with a cup or compass; then redraw digitally"],
        ],
        [3.6, 2.2, 5.2, 5.5], caption="Tools for drawing Venn diagrams", size=8.6,
    )
    doc.h2("1.3 draw.io (diagrams.net), step by step")
    doc.steps([
        "Open app.diagrams.net, create a blank diagram, and save the file first (this is your editable source).",
        "From **General**, drag an **Ellipse**. In the **Format** panel set Width and Height equal (for example 300 by 300) so it is a circle.",
        "Set **Fill** to a colour and **Opacity** to about 30 percent (Format > Style > Opacity or the Fill slider). Set the **Line** colour to the same hue, thicker.",
        "Select the circle, press **Ctrl+D** to duplicate, and drag the copy so the two overlap by about one third of the diameter. Hold **Alt** while dragging to move without snapping.",
        "Duplicate again and place the third circle below the other two, centred between them. The three circles now form a triangle with a shared centre.",
        "Add **text boxes** (Text from General) for set names outside the circles and for each region inside. Keep each phrase to two or three short lines.",
        "Use **Arrange > Align > Center** and **Arrange > Distribute** to keep the circles symmetric.",
        "Check the text is readable where the colours blend; if not, make the text bold or darker, or reduce opacity.",
        "**File > Export as > PNG**: zoom 200 percent or DPI 300, border width 10. Also export SVG for the report.",
    ])
    doc.h2("1.4 PowerPoint or Google Slides, step by step")
    doc.steps([
        "Use a blank slide. Insert **Shapes > Oval**; hold **Shift** while dragging to make a circle.",
        "Right-click > **Format Shape**: set **Fill** to a solid colour and **Transparency** to 70 percent; set the outline colour.",
        "Copy and paste twice; move the circles so they overlap. In PowerPoint, **Arrange > Align** to centre them.",
        "Insert text boxes for the labels. Use a white or no-fill text box so words stay readable.",
        "Optional exact overlap shapes: select two circles, **Shape Format > Merge Shapes > Intersect** to cut out the overlap as its own shape, which you can colour and label separately.",
        "**File > Export > PNG** (or Save as picture) at the highest quality.",
    ])
    doc.h2("1.5 LaTeX with TikZ (matches the proposal)")
    doc.p("The proposal is written in LaTeX and already uses TikZ for its Gantt charts, so a TikZ Venn diagram needs no new package beyond `tikz`. "
          "The snippet below was compiled and checked (file `Docs/diagrams/venn-tikz-example.tex`). Change the labels and positions to suit.")
    doc.code(BODY)
    doc.bullets([
        "`\\fill[...,opacity=.30]` draws a see-through circle, so overlaps look darker automatically; `\\draw` adds the outline.",
        "Centres at (-1.2, 0.7), (1.2, 0.7) and (0, -1.4) with radius 2.2 make three equal circles overlapping about one third; move them closer for a bigger overlap.",
        "Put set names with `\\node` outside the circles and overlap labels with `\\node` inside, using `align=center` and `\\\\` for line breaks.",
        "To use it as a figure, wrap it in `\\begin{figure}` with a `\\caption{}` as the proposal does for other figures.",
    ])
    doc.h2("1.6 Python, for reproducible figures")
    doc.p("The figures in the Venn document are drawn by `Docs/diagrams/make_other.py` with matplotlib circles at 30 percent opacity. If you prefer a ready library:")
    doc.code("""# pip install matplotlib matplotlib-venn
from matplotlib import pyplot as plt
from matplotlib_venn import venn3

venn3(subsets=(1, 1, 1, 1, 1, 1, 1),            # equal-size regions, so labels fit
      set_labels=("Bangla-first", "Moderated and dated", "Offline and priced"))
plt.savefig("venn.png", dpi=300, bbox_inches="tight")""")
    doc.p("With `matplotlib-venn`, region labels are changed through `venn3(...).get_label_by_id('111').set_text('Abhijatri')` (ids are binary strings: '100' set A only, '110' A and B, '111' all three).")
    doc.h2("1.7 Make it readable and accessible")
    doc.bullets([
        "Use a colour-blind-safe palette. The Abhijatri figures and the TikZ snippet use blue (#0072B2), green (#009E73) and orange (#E69F00) from the Okabe-Ito set.",
        "Never rely on colour alone: every region carries a text label.",
        "Keep text at 8 pt or larger after the figure is scaled to the page width.",
        "Keep the title short and say what the diagram shows. Put caveats in a one-line note under the title, as the Abhijatri figures do.",
        "Number the figure, caption it, and mention it in the text.",
        "Test the diagram in black and white: it should still make sense.",
    ])
    doc.h2("1.8 Checklist before you submit")
    doc.table(
        ["Done", "Check"],
        [["[  ]", c] for c in [
            "Every set has a clear noun-phrase name",
            "Every region has a short, true label (or is stated to be empty)",
            "Prototype and planned items are marked",
            "Colours are distinguishable and not the only signal",
            "Text is readable at A4 width",
            "The figure has a number, a caption and is referred to in the text",
            "The editable source file is saved next to the image",
            "No unsupported numbers or competitor claims",
        ]],
        [1.4, 15.1],
    )
    assert "\\node" in BODY and len(BODY) > 500, "TikZ snippet missing"
    OUT.parent.mkdir(exist_ok=True)
    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
