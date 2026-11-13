"""Offline File, Document (PDF/DOCX/TXT), Spreadsheet (XLSX/CSV), and Safe Calculator Engine."""

from __future__ import annotations

import ast
import csv
import math
import operator
import shutil
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import docx
import openpyxl
from pypdf import PdfReader

from ..security.permission_engine import PermissionEngine
from ..security.prompt_guard import PromptInjectionShield

_SAFE_OPERATORS: dict[type[Any], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_MATH_FUNCS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "ceil": math.ceil,
    "floor": math.floor,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "mean": statistics.mean,
    "median": statistics.median,
    "pi": math.pi,
    "e": math.e,
}


def safe_calculate(expression: str) -> float | int:
    """Evaluate a mathematical expression safely via AST inspection (no eval() code execution)."""
    expr = (expression or "").strip().replace("^", "**")
    if len(expr) > 500:
        raise ValueError("Expression exceeds maximum length")

    tree = ast.parse(expr, mode="eval")

    def _eval_node(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.List) or isinstance(node, ast.Tuple):
            return [_eval_node(elt) for elt in node.elts]
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPERATORS:
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Exponent too large")
            return _SAFE_OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[type(node.op)](_eval_node(node.operand))
        if isinstance(node, ast.Name) and node.id in _SAFE_MATH_FUNCS:
            val = _SAFE_MATH_FUNCS[node.id]
            if isinstance(val, (int, float)):
                return val
            raise ValueError(f"Function '{node.id}' must be called")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _SAFE_MATH_FUNCS:
            fn = _SAFE_MATH_FUNCS[node.func.id]
            if not callable(fn):
                raise ValueError(f"'{node.func.id}' is not callable")
            args = [_eval_node(arg) for arg in node.args]
            return fn(*args)
        raise ValueError(f"Unsupported syntax in calculation: {type(node).__name__}")

    res = _eval_node(tree)
    return round(res, 10) if isinstance(res, float) else res


class FileIntelligenceEngine:
    """Local file search, TXT/PDF/DOCX reading & creation, and XLSX/CSV spreadsheet processing."""

    def __init__(
        self,
        permissions: PermissionEngine,
        prompt_shield: PromptInjectionShield,
    ) -> None:
        self.permissions = permissions
        self.prompt_shield = prompt_shield

    def search_files(
        self,
        root_dir: Path,
        pattern: str = "*",
        content_query: str | None = None,
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        self.permissions.require_permission("local_file_access", actor="file_agent", action_desc=f"search {root_dir}")
        root = Path(root_dir)
        if not root.exists():
            return []

        results: list[dict[str, Any]] = []
        skipped_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__"}
        for path in root.rglob(pattern):
            if any(part in skipped_dirs for part in path.parts):
                continue
            if not path.is_file():
                continue
            snippet = ""
            if content_query:
                try:
                    if path.stat().st_size <= 2 * 1024 * 1024:
                        txt = path.read_text(encoding="utf-8", errors="ignore")
                        idx = txt.lower().find(content_query.lower())
                        if idx == -1:
                            continue
                        start = max(0, idx - 40)
                        snippet = txt[start : idx + len(content_query) + 60].replace("\n", " ")
                    else:
                        continue
                except OSError:
                    continue

            stat = path.stat()
            results.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "snippet": snippet,
                }
            )
            if len(results) >= max_results:
                break
        return results

    def write_text_file(self, file_path: Path, content: str, create_backup: bool = True) -> dict[str, Any]:
        self.permissions.require_permission("local_file_access", actor="file_agent", action_desc=f"write {file_path}")
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        backup_path = None
        if create_backup and target.exists():
            backup_path = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup_path)
        target.write_text(content, encoding="utf-8")
        return {
            "path": str(target),
            "bytes_written": target.stat().st_size,
            "backup_path": str(backup_path) if backup_path else None,
        }

    def read_document(self, file_path: Path, sanitize_for_ai: bool = False) -> dict[str, Any]:
        """Read TXT, MD, JSON, CSV, PDF, DOCX, or XLSX into structured text and metadata."""
        self.permissions.require_permission("local_file_access", actor="file_agent", action_desc=f"read {file_path}")
        target = Path(file_path)
        if not target.exists():
            raise FileNotFoundError(f"Document not found: {target}")

        ext = target.suffix.lower()
        metadata: dict[str, Any] = {"extension": ext, "size_bytes": target.stat().st_size}

        if ext == ".pdf":
            reader = PdfReader(str(target))
            pages_text = [(page.extract_text() or "") for page in reader.pages]
            raw_text = "\n\n".join(pages_text).strip()
            metadata["page_count"] = len(reader.pages)
        elif ext == ".docx":
            doc = docx.Document(str(target))
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            for tbl in doc.tables:
                for row in tbl.rows:
                    paras.append(" | ".join(cell.text.strip() for cell in row.cells))
            raw_text = "\n".join(paras)
            metadata["paragraph_count"] = len(doc.paragraphs)
        elif ext in {".xlsx", ".xlsm"}:
            wb = openpyxl.load_workbook(str(target), data_only=True)
            lines: list[str] = []
            metadata["sheets"] = wb.sheetnames
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                lines.append(f"=== Sheet: {sheet_name} ===")
                for row in ws.iter_rows(values_only=True):
                    if any(v is not None for v in row):
                        lines.append("\t".join("" if v is None else str(v) for v in row))
            wb.close()
            raw_text = "\n".join(lines)
        elif ext == ".csv":
            with target.open("r", encoding="utf-8", errors="replace", newline="") as f:
                rows = list(csv.reader(f))
            metadata["row_count"] = len(rows)
            raw_text = "\n".join(", ".join(r) for r in rows)
        else:
            raw_text = target.read_text(encoding="utf-8", errors="replace")

        injection_detected = False
        if sanitize_for_ai:
            shielded = self.prompt_shield.inspect_and_wrap(raw_text, source=f"file:{target.name}")
            text_out = shielded.safe_text
            injection_detected = shielded.injection_detected
        else:
            text_out = raw_text

        return {
            "path": str(target),
            "text": text_out,
            "metadata": metadata,
            "injection_detected": injection_detected,
        }

    def create_docx(self, file_path: Path, title: str, paragraphs: list[str]) -> Path:
        self.permissions.require_permission("local_file_access", actor="file_agent", action_desc=f"create docx {file_path}")
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        doc = docx.Document()
        doc.add_heading(title, level=1)
        for p in paragraphs:
            doc.add_paragraph(p)
        doc.save(str(target))
        return target

    def create_simple_pdf(self, file_path: Path, title: str, lines: list[str]) -> Path:
        """Create a standards-compliant single-page PDF document offline with zero external binaries."""
        self.permissions.require_permission("local_file_access", actor="file_agent", action_desc=f"create pdf {file_path}")
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        def _esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        stream_cmds = ["BT", "/F1 16 Tf", "50 750 Td", f"({_esc(title)}) Tj", "/F1 11 Tf"]
        for line in lines[:42]:
            stream_cmds.append("0 -16 Td")
            stream_cmds.append(f"({_esc(line[:95])}) Tj")
        stream_cmds.append("ET")
        stream_bytes = "\n".join(stream_cmds).encode("latin-1", errors="replace")

        objects: list[bytes] = [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
            f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii") + stream_bytes + b"\nendstream\nendobj\n",
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        ]

        out = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(len(out))
            out.extend(obj)
        xref_pos = len(out)
        out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
        out.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
        out.extend(
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
        )
        target.write_bytes(bytes(out))
        return target

    def create_or_analyze_spreadsheet(
        self,
        file_path: Path,
        headers: list[str] | None = None,
        rows: list[list[Any]] | None = None,
        numeric_column_index: int | None = None,
    ) -> dict[str, Any]:
        """Write and/or analyze an XLSX spreadsheet offline."""
        self.permissions.require_permission("local_file_access", actor="data_agent", action_desc=f"xlsx {file_path}")
        target = Path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        if headers is not None or rows is not None:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Data"
            if headers:
                ws.append(headers)
            for r in rows or []:
                ws.append(r)
            wb.save(str(target))
            wb.close()

        wb = openpyxl.load_workbook(str(target), data_only=True)
        ws = wb.active
        all_rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()

        stats_summary: dict[str, Any] = {"row_count": max(0, len(all_rows) - 1), "headers": all_rows[0] if all_rows else []}
        if numeric_column_index is not None and len(all_rows) > 1:
            nums = [
                float(r[numeric_column_index])
                for r in all_rows[1:]
                if numeric_column_index < len(r) and isinstance(r[numeric_column_index], (int, float))
            ]
            if nums:
                stats_summary["sum"] = round(sum(nums), 4)
                stats_summary["average"] = round(statistics.mean(nums), 4)
                stats_summary["min"] = min(nums)
                stats_summary["max"] = max(nums)
        return {"path": str(target), "stats": stats_summary}
