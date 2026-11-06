"""Builds Docs/internal/Abhijatri-Proposal-Coverage.docx: the team's check of the proposal against the nine required points
and the SRS elements. This was sections 1 to 3 of the SRS completion document; the SRS itself is now standalone (review issue S23).
"""

from pathlib import Path

from docx_helpers import Doc

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "internal" / "Abhijatri-Proposal-Coverage.docx"

GREEN, AMBER, RED = "E3F3EA", "FFF4D6", "F9DFD8"


def main() -> None:
    doc = Doc(
        "Proposal Coverage Check",
        "Internal team checklist: the nine required proposal points and the SRS elements (not for submission)",
        [
            ("Project", "Abhijatri (Team ChoturMatra, CSE 3102)"),
            ("Document", "Internal checklist; the submitted SRS is Docs/Abhijatri-SRS-Completion.docx"),
            ("Version", "1.1, 31 October 2026"),
        ],
        "Abhijatri: proposal coverage (internal)",
    )
    doc.contents()
    # ------------------------------------------------------------------ 1
    doc.h1("1. Summary")
    doc.p("The proposal already contains **all nine** points your instructor requires. Each is present and substantial. What it does not contain is the rest of a Software Requirements Specification (SRS): "
          "a glossary, constraints, assumptions, external interface requirements, data requirements, detailed use case descriptions, state and sequence diagrams, a data flow diagram, a traceability matrix, and revision history. "
          "It was also written on 12 October 2026, before the review, moderation, notification and account features were built, so some statements need an \"as built\" note.")
    doc.table(
        ["Question", "Answer"],
        [
            ["Are the nine required proposal points present?", "Yes, all nine (section 2)."],
            ["Is there a use case diagram?", "Yes: the UML use case model with four actors and ten packages (proposal section \"Primary Use Cases\"). The SRS (3.2) now uses an as-built use case diagram with the SRS user classes."],
            ["Is there a complete SRS?", "Not yet. 14 standard SRS elements are missing or only partly covered (section 3). The standalone SRS (Abhijatri-SRS-Completion.docx) supplies them."],
            ["Is there a data flow diagram?", "No in the proposal. It is now in Abhijatri-DFD.docx (context, level 0, level 1 and level 2)."],
            ["Does the proposal match what was built?", "Mostly in intent, but with differences listed in SRS section 5 (for example Supabase Auth instead of self-managed password hashing, and the offline features still being prototypes)."],
        ],
        [6.0, 10.5], caption="Summary of findings",
    )
    doc.note("**How to use this document.** The SRS sections are in the standalone SRS. "
             "Where something is a prototype or not built, the text says so plainly; do not remove those statements, because they are what the repository supports.")

    # ------------------------------------------------------------------ 2
    doc.h1("2. The nine required proposal points: coverage")
    fills = {(i, 1): GREEN for i in range(9)}
    doc.table(
        ["#", "Required point", "Where in the proposal", "Assessment and what to improve"],
        [
            ["1", "Executive Summary", "Section 1, Executive Summary", "Present. Covers the problem, the solution and the semester outcome (a tested PWA with five seeded destinations). Improve: add one sentence of as-built status and one headline measure."],
            ["2", "Problem Statement", "Section 2, five subsections (fragmented information, unclear costs, weak connectivity, Bangla-first support, trust and freshness)", "Present and well structured. Improve: add one or two cited sources or survey figures if available, because the section states the gap without evidence."],
            ["3", "Objectives and Goals", "Section 3, objectives O1 to O8 with completion measures", "Present and measurable (for example 10 of 10 airplane-mode tests, at least eight consenting participants). Improve: add the results as they become known; note that O4 depends on offline features that are not built yet."],
            ["4", "Functional Requirements", "Section 4: core and future features, user roles, FR01 to FR17 catalogue, cost planner rules, use case model, user stories, MVP exclusions", "Present and the strongest section. Improve: use case specifications and an as-built status per requirement are in SRS 3.4 and 3.2."],
            ["5", "Non-functional Requirements", "Section 5, table with performance, security, reliability, scalability, usability and accessibility, maintainability, portability, privacy", "Present with acceptance measures, including the 50-user load target (2 s at the 95th percentile) and WCAG 2.2 AA. SRS 3.6 adds an availability target and the evidence to date."],
            ["6", "Stakeholders", "Section 6, seven stakeholder groups with interest and engagement", "Present. Improve: add influence and interest levels and who is the decision owner."],
            ["7", "Timeline / Milestones", "Section 7: milestones M1 to M4 and gate G1, formal testing phase, Gantt chart with dependencies and effort", "Present and detailed. Improve: add a \"planned versus actual\" column as of the submission date."],
            ["8", "Risk Assessment", "Section 8, 13 risks with level, early warning, mitigation and owner", "Present. The third-party dependency risk with likelihood and impact is in SRS 2.7. Still to do in the proposal: scores for the other risks."],
            ["9", "Feasibility Study", "Section 9: technical, economic (BDT 6,000 ceiling), schedule, operational and ethical", "Present, covers all three required kinds plus one more. The hosting and service cost table is in SRS 2.7."],
        ],
        [0.8, 3.2, 5.0, 7.5], caption="Coverage of the nine required points", size=8.6, fills=fills,
    )

    # ------------------------------------------------------------------ 3
    doc.h1("3. What a complete SRS adds: gap analysis")
    srs = [
        ["Introduction", "Purpose of the document", "Partly", "Executive Summary and Scope Decision", "SRS 1.1"],
        ["Introduction", "Scope of the product", "Yes", "Scope Decision, MVP exclusions", "Reuse; SRS 1.2 restates it"],
        ["Introduction", "Definitions, acronyms, abbreviations (glossary)", "Missing", "none (0 mentions)", "SRS 1.3"],
        ["Introduction", "References", "Missing", "none", "SRS 1.4"],
        ["Overall description", "Product perspective and system context", "Partly", "Architecture is mentioned only in feasibility", "SRS 2.1 with the context DFD"],
        ["Overall description", "Product functions", "Yes", "Core and future features", "SRS 2.2 maps them to processes"],
        ["Overall description", "User classes and characteristics", "Yes", "User roles table", "SRS 2.3 adds Verified Member, moderator, superadmin, ops"],
        ["Overall description", "Operating environment", "Partly", "Portability row", "SRS 2.4"],
        ["Overall description", "Design and implementation constraints", "Missing", "none", "SRS 2.5"],
        ["Overall description", "Assumptions and dependencies", "Partly", "3 scattered mentions", "SRS 2.6"],
        ["Specific requirements", "External interface requirements (user, software, hardware, communications)", "Missing", "none", "SRS 3.1"],
        ["Specific requirements", "Functional requirements", "Yes", "FR01 to FR17", "Reuse; SRS 3.2 adds status as built"],
        ["Specific requirements", "Non-functional requirements", "Yes", "Eight categories", "Reuse; SRS 3.6 adds targets and evidence"],
        ["Specific requirements", "Data requirements (data model, retention)", "Missing", "none", "SRS 3.3 with the ER diagram"],
        ["Specific requirements", "Use case specifications", "Partly", "Diagram and user stories only", "SRS 3.4"],
        ["Specific requirements", "Behaviour models (state, sequence)", "Missing", "none", "SRS 3.5 (state and sequence)"],
        ["Appendices", "Data flow diagram", "Missing", "none", "SRS Appendix A and Abhijatri-DFD.docx"],
        ["Appendices", "Requirements traceability matrix", "Partly", "User stories trace to FR", "SRS 4: FR to use case to API to test"],
        ["Appendices", "Verification plan", "Yes", "Formal testing table and phases", "Reuse"],
        ["Appendices", "Revision history and approval", "Missing", "none", "SRS Appendix B"],
    ]
    fills = {}
    for i, r in enumerate(srs):
        fills[(i, 2)] = {"Yes": GREEN, "Partly": AMBER, "Missing": RED}[r[2]]
    doc.table(["SRS part", "Element", "Status in the proposal", "What exists", "Supplied by"], srs, [2.6, 4.7, 2.0, 3.8, 3.5], caption="SRS elements: present, partly present, missing", size=8.4, fills=fills)
    missing = sum(1 for r in srs if r[2] == "Missing")
    partly = sum(1 for r in srs if r[2] == "Partly")
    doc.p(f"Of {len(srs)} elements, {len(srs) - missing - partly} are present, {partly} are partly present and {missing} are missing. "
          "The 14 gaps (missing plus partly present) are all filled by the standalone SRS.")


    OUT.parent.mkdir(exist_ok=True)
    doc.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
