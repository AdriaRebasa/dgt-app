from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument
from PyQt6.QtPrintSupport import QPrinter


def render_table_to_html(
    headers: List[str],
    rows: List[List[str]],
    title: str,
    chart_base64: Optional[str] = None,
) -> str:
    header_html = "".join([f"<th>{h}</th>" for h in headers])
    body_rows = []
    for row in rows:
        cells = "".join([f"<td>{c}</td>" for c in row])
        body_rows.append(f"<tr>{cells}</tr>")
    body_html = "".join(body_rows)
    chart_html = f'<img src="data:image/png;base64,{chart_base64}" style="width: 100%; margin-top: 16px;" />' if chart_base64 else ""
    return f"""
    <html>
    <head>
      <style>
        body {{ font-family: Arial, sans-serif; font-size: 10pt; }}
        h1 {{ font-size: 14pt; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #333; padding: 4px; text-align: left; }}
        th {{ background: #efefef; }}
      </style>
    </head>
    <body>
      <h1>{title}</h1>
      <table>
        <thead><tr>{header_html}</tr></thead>
        <tbody>{body_html}</tbody>
      </table>
      {chart_html}
    </body>
    </html>
    """


def export_html_to_pdf(html: str, output_path: str) -> None:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(output_path)
    printer.setPageMargins(12, 12, 12, 12, QPrinter.Unit.Millimeter)

    doc = QTextDocument()
    doc.setHtml(html)
    doc.print(printer)
