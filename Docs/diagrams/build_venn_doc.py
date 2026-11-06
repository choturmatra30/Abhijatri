"""Builds Docs/Abhijatri-Venn-Diagram.docx: the three overlap (Venn) diagrams and how to read them.

The drawing guide (tools, steps, TikZ snippet) is the internal document built by build_venn_guide.py.
"""

from pathlib import Path

from docx_helpers import Doc

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "Abhijatri-Venn-Diagram.docx"
GREEN, AMBER, RED = "E3F3EA", "FFF4D6", "F9DFD8"


def status_fills(rows, col):
    return {(i, col): GREEN if r[col].lower().startswith("built") else (RED if r[col].lower().startswith(("planned", "not")) else AMBER)
            for i, r in enumerate(rows)}


def main() -> None:
    doc = Doc(
        "Venn Diagrams",
        "What Abhijatri combines, where it sits among existing kinds of tools, and how the team's work overlaps",
        [
            ("Project", "Abhijatri: a Bangla-first, offline-ready community travel platform for Bangladesh (Team ChoturMatra, CSE 3102)"),
            ("Document", "Three Venn diagrams: what Abhijatri combines, where it sits among existing tools, and how the team's work overlaps"),
            ("Date", "31 October 2026"),
            ("Basis", "Proposal (problem statement, objectives, roles) and Docs/Implemented.md for what is built"),
        ],
        "Abhijatri: Venn Diagrams",
    )
    doc.contents()

    doc.h1("1. Venn 1: What Abhijatri Combines")
    doc.p("The proposal's problem statement found that travellers in Bangladesh meet these three needs only in separate places. "
          "Built today: the Bangla interface, moderated reviews and advisory freshness labels. Offline use and pricing are a "
          "prototype or planned.")
    doc.figure(HERE / "venn-product.png", "Venn 1: The Three Traveller Needs That Abhijatri Combines (each region marked built, prototype or planned)", 16.0, 15.5)
    rows = [
        ["Bangla-First (alone)", "A Bangla default interface with English selectable", "Built (no automated test of the language switch yet)"],
        ["Moderated and Dated (alone)", "Reviews checked by moderators before they appear; advisories with a source date and a freshness state", "Built and tested"],
        ["Offline and Priced (alone)", "Itemised cost estimates and destination packs that work without a signal", "Prototype screens only"],
        ["Bangla-First and Moderated", "Bangla destination content and reviews shown with their freshness labels", "Built"],
        ["Bangla-First and Offline", "Bangla pages readable without a connection", "Planned (no service worker or IndexedDB yet)"],
        ["Moderated and Priced", "Estimates built from prices that carry a source and a date", "Planned with the price catalogue"],
        ["All three: Abhijatri", "A Bangla-first, moderated and priced trip guide that works offline", "The project goal; partly built"],
    ]
    doc.table(["Region", "What It Means", "Status"], rows, [4.4, 7.6, 4.5], caption="Venn 1: What Each Region Means", size=9.5, fills=status_fills(rows, 2), keep_together=True)

    doc.h1("2. Venn 2: Where Abhijatri Sits Among Existing Tools")
    doc.figure(HERE / "venn-landscape.png", "Venn 2: Existing Travel Tools and Where Abhijatri Sits (capabilities, not products)", 16.0, 15.5)
    doc.p("The circles are capabilities, not products. Each kind of tool sits in the one region it covers well, and no kind of tool "
          "compared sits in an overlap. Abhijatri aims for the centre; its offline part is still planned, so the centre says so.")
    rows = [
        ["Bangla-First only", "Social media travel groups and blogs", "Bangla and local knowledge, but posts are not moderated or dated"],
        ["Moderated and Dated only", "Booking and guide sites", "Checked listings and reviews, mostly in English and online only"],
        ["Works Offline only", "Maps and offline apps", "Work without a signal, but carry little local travel advice and no trip costs"],
        ["Any two capabilities", "None of the tool types compared", "This gap is the problem the proposal describes"],
        ["All three", "Abhijatri", "Bangla-first and moderated parts built; offline planned"],
    ]
    doc.table(["Region", "Kind of Tool", "Why It Sits There"], rows, [4.0, 4.6, 7.9], caption="Venn 2: Kinds of Tools in Each Region", size=9.5, keep_together=True)

    doc.h1("3. Venn 3: Team Responsibilities")
    doc.figure(HERE / "venn-roles.png", "Venn 3: Team Responsibilities and Shared Work (the centre is the leader's coordination role)", 16.0, 15.5)
    doc.p("The three circles are the specialist roles in the proposal. The project leader is not a fourth set: the centre is the leader's "
          "coordination role over the work all three share. The table gives the same information in responsible-and-accountable form.")
    rows = [
        ["API contract and error handling", "Frontend and Backend", "Leader"],
        ["Offline and real-device tests", "Frontend and Quality", "Leader"],
        ["Integration and security tests", "Backend and Quality", "Leader"],
        ["Scope, destination content, estimator rules (planned), documents", "Leader", "Leader"],
        ["End-to-end review flow", "All three", "Leader"],
    ]
    doc.table(["Shared Work", "Responsible", "Accountable"], rows, [8.5, 4.5, 3.5], caption="Venn 3: Shared Work by Role", size=9.5, keep_together=True)
    doc.p("Roles: Frontend and offline, Abdullah Bin Sorwar Choudhury; Backend and data, Syed Muhtasim Alam; Quality assurance, "
          "Md. Irfan Iqbal; Project leader, Shahriar Islam.")

    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
