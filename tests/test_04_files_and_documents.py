"""QA Scenarios #12 & #13: Local File Operations, DOCX, Spreadsheets (XLSX), Calculator & PDF Processing."""

from __future__ import annotations

from pathlib import Path

from nexus_ultron.intelligence.file_intelligence import safe_calculate
from nexus_ultron.runtime import NexusUltronRuntime


def test_12_local_files_docx_spreadsheet_and_calculator(offline_runtime: NexusUltronRuntime, tmp_path: Path) -> None:
    """Test #12: File creation, backup-on-edit, search, DOCX, XLSX analytics, Notes/Reminders & Calculator."""
    work = tmp_path / "docs_test"

    # Write & update text file with automatic .bak safeguard
    txt_file = work / "notes.txt"
    offline_runtime.file_intel.write_text_file(txt_file, "Version 1: Alpha")
    res_v2 = offline_runtime.file_intel.write_text_file(txt_file, "Version 2: Beta inventory keyword", create_backup=True)
    assert Path(res_v2["backup_path"]).exists()

    # Search by content substring
    hits = offline_runtime.file_intel.search_files(work, pattern="*.txt", content_query="inventory")
    assert len(hits) == 1 and hits[0]["name"] == "notes.txt"

    # DOCX creation & extraction
    docx_file = offline_runtime.file_intel.create_docx(
        work / "spec.docx",
        "NEXUS Specification",
        ["Autonomous local execution verified.", "Zero cloud dependency for offline docs."],
    )
    read_docx = offline_runtime.file_intel.read_document(docx_file)
    assert "Autonomous local execution verified." in read_docx["text"]

    # XLSX Spreadsheet creation & column analytics
    xlsx_res = offline_runtime.file_intel.create_or_analyze_spreadsheet(
        work / "sales.xlsx",
        headers=["Quarter", "Units"],
        rows=[["Q1", 120], ["Q2", 180], ["Q3", 300]],
        numeric_column_index=1,
    )
    assert xlsx_res["stats"]["sum"] == 600.0
    assert xlsx_res["stats"]["average"] == 200.0

    # Notes & Reminders + Safe Calculator
    rem = offline_runtime.memory.add_note_or_reminder("Deploy Release", "Run full QA suite", item_type="reminder")
    offline_runtime.memory.toggle_reminder_completed(rem["id"], True)
    assert offline_runtime.memory.list_notes_reminders("reminder")[0]["completed"] == 1
    assert safe_calculate("sqrt(144) + mean([10, 20, 30])") == 32.0


def test_13_pdf_creation_and_extraction(offline_runtime: NexusUltronRuntime, tmp_path: Path) -> None:
    """Test #13: Offline PDF generation and pypdf multi-line text extraction."""
    pdf_path = offline_runtime.file_intel.create_simple_pdf(
        tmp_path / "verification_report.pdf",
        "NEXUS ULTRON QA REPORT",
        [
            "Document Engine: Verified Offline",
            "Hardware Baseline: 8 GB RAM Compatible",
        ],
    )
    assert pdf_path.exists()
    extracted = offline_runtime.file_intel.read_document(pdf_path, sanitize_for_ai=True)
    assert extracted["metadata"]["page_count"] == 1
    assert "NEXUS ULTRON QA REPORT" in extracted["text"]
    assert "Verified Offline" in extracted["text"]
