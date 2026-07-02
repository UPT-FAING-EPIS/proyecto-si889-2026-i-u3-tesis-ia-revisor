from __future__ import annotations

import io
import re
import unicodedata
from datetime import datetime
from html import escape as html_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 2.8 * cm
RIGHT_MARGIN = 2.3 * cm
TOP_MARGIN = 2.4 * cm
BOTTOM_MARGIN = 2.0 * cm
USABLE_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
ROMAN_SECTION_PATTERN = re.compile(r"^(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\.\s+", re.IGNORECASE)
NUMERIC_SUBSECTION_PATTERN = re.compile(r"^\d+\.\d+")


UNICODE_REPLACEMENTS = {
    "\u00a0": " ",
    "\u00ad": "",
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2022": "-",
    "\u00d7": "x",
    "\u03b1": "alfa",
}


def _clean_text(value: str | None) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    for source, replacement in UNICODE_REPLACEMENTS.items():
        text = text.replace(source, replacement)
    return "".join(character for character in text if character in "\n\t" or ord(character) >= 32)


def _plain_markdown(value: str | None) -> str:
    text = _clean_text(value)
    text = re.sub(r"^#{1,6}\s*", "", text.strip())
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip(" :-")


def _normalize_ascii(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", _plain_markdown(value))
    return text.encode("ascii", "ignore").decode("ascii").lower()


def _clean_extracted_value(value: str | None) -> str:
    return _plain_markdown(value).strip().strip('"').strip("'").strip()


def _inline_markup(value: str | None) -> str:
    text = _clean_text(value).strip()
    text = html_escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    return text


def _safe_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text.lower()).strip("_")
    return slug[:70] or "plan_de_tesis"


def _extract_year(plan_text: str) -> str:
    years = [int(match) for match in re.findall(r"\b(20\d{2})\b", plan_text)]
    if years:
        return str(max(years))
    return str(datetime.now().year)


def _extract_numbered_field(plan_text: str, section_number: str, label: str) -> str:
    lines = plan_text.splitlines()
    normalized_label = _normalize_ascii(label)

    for index, line in enumerate(lines):
        normalized_line = _normalize_ascii(line)
        if section_number not in normalized_line or normalized_label not in normalized_line:
            continue

        window = "\n".join(lines[index : index + 5])
        quoted = re.search(r'"([^"]{12,260})"', _clean_text(window))
        if quoted:
            return _clean_extracted_value(quoted.group(1))

        plain_line = _plain_markdown(line)
        if ":" in plain_line:
            candidate = plain_line.split(":", 1)[1].strip()
            if candidate and "[" not in candidate:
                return _clean_extracted_value(candidate)

        follow_up_values: list[str] = []
        for next_line in lines[index + 1 : index + 6]:
            candidate = _clean_extracted_value(next_line)
            if not candidate:
                continue
            normalized_candidate = _normalize_ascii(candidate)
            if (
                re.match(r"^\d+(?:\.\d+)?\s+", normalized_candidate)
                or ROMAN_SECTION_PATTERN.match(candidate)
                or normalized_candidate.startswith("nota de consistencia")
            ):
                break
            if "[" in candidate:
                continue
            follow_up_values.append(candidate)
            if section_number != "1.4" or len(follow_up_values) >= 2:
                break

        if follow_up_values:
            return "; ".join(follow_up_values)

    return ""


def _extract_title(plan_text: str, fallback_title: str) -> str:
    title = _extract_numbered_field(plan_text, "1.1", "titulo")
    if title:
        return title
    for line in plan_text.splitlines()[:35]:
        plain_line = _plain_markdown(line)
        normalized_line = _normalize_ascii(plain_line)
        if normalized_line.startswith("titulo") and ":" in plain_line:
            candidate = plain_line.split(":", 1)[1].strip()
            if len(candidate) >= 8 and "[" not in candidate:
                return _clean_extracted_value(candidate)
    return _plain_markdown(fallback_title) or "Plan de trabajo de investigacion"


def _extract_author(plan_text: str, user_email: str | None) -> str:
    author = _extract_numbered_field(plan_text, "1.4", "autor")
    if author:
        return author
    if user_email:
        return user_email
    return "Por validar"


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [_plain_markdown(cell) for cell in stripped.split("|")]


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


class ThesisPlanDocTemplate(BaseDocTemplate):
    def __init__(self, buffer: io.BytesIO, document_label: str):
        frame = Frame(
            LEFT_MARGIN,
            BOTTOM_MARGIN,
            USABLE_WIDTH,
            PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN,
            id="normal",
        )
        super().__init__(
            buffer,
            pagesize=A4,
            leftMargin=LEFT_MARGIN,
            rightMargin=RIGHT_MARGIN,
            topMargin=TOP_MARGIN,
            bottomMargin=BOTTOM_MARGIN,
        )
        self.document_label = document_label
        self.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=self._draw_page)])

    def afterFlowable(self, flowable) -> None:  # noqa: ANN001
        if not isinstance(flowable, Paragraph):
            return

        style_name = flowable.style.name
        if style_name == "BodyHeading1":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))
        elif style_name == "BodyHeading2":
            self.notify("TOCEntry", (1, flowable.getPlainText(), self.page))

    @staticmethod
    def _draw_page(canvas, doc) -> None:  # noqa: ANN001
        if doc.page == 1:
            return

        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#8a8a8a"))
        canvas.setLineWidth(0.4)
        canvas.line(LEFT_MARGIN, 1.55 * cm, PAGE_WIDTH - RIGHT_MARGIN, 1.55 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#4f4f4f"))
        canvas.drawString(LEFT_MARGIN, 1.2 * cm, getattr(doc, "document_label", "DOCUMENTO ACADEMICO"))
        canvas.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 1.2 * cm, f"Pagina {doc.page}")
        canvas.restoreState()


class ThesisPlanPdfService:
    def __init__(self) -> None:
        self.styles = self._build_styles()

    @staticmethod
    def _build_styles() -> dict[str, ParagraphStyle]:
        sample = getSampleStyleSheet()
        styles = {
            "cover_institution": ParagraphStyle(
                "CoverInstitution",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=18,
                alignment=TA_CENTER,
                spaceAfter=2,
            ),
            "cover_label": ParagraphStyle(
                "CoverLabel",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=16,
                alignment=TA_CENTER,
                spaceBefore=18,
                spaceAfter=10,
            ),
            "cover_title": ParagraphStyle(
                "CoverTitle",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=15,
                leading=21,
                alignment=TA_CENTER,
                spaceBefore=20,
                spaceAfter=20,
            ),
            "cover_text": ParagraphStyle(
                "CoverText",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=11,
                leading=16,
                alignment=TA_CENTER,
                spaceAfter=4,
            ),
            "toc_title": ParagraphStyle(
                "TocTitle",
                parent=sample["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=18,
                alignment=TA_CENTER,
                spaceAfter=18,
            ),
            "BodyHeading1": ParagraphStyle(
                "BodyHeading1",
                parent=sample["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=17,
                alignment=TA_LEFT,
                spaceBefore=12,
                spaceAfter=8,
            ),
            "BodyHeading2": ParagraphStyle(
                "BodyHeading2",
                parent=sample["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=11.2,
                leading=15,
                alignment=TA_LEFT,
                spaceBefore=9,
                spaceAfter=5,
            ),
            "BodyHeading3": ParagraphStyle(
                "BodyHeading3",
                parent=sample["Heading3"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=13,
                alignment=TA_LEFT,
                spaceBefore=7,
                spaceAfter=4,
            ),
            "BodyText": ParagraphStyle(
                "BodyText",
                parent=sample["BodyText"],
                fontName="Helvetica",
                fontSize=9.6,
                leading=13.2,
                alignment=TA_JUSTIFY,
                spaceAfter=6,
            ),
            "ListText": ParagraphStyle(
                "ListText",
                parent=sample["BodyText"],
                fontName="Helvetica",
                fontSize=9.5,
                leading=13,
                leftIndent=16,
                firstLineIndent=-10,
                spaceAfter=4,
            ),
            "TableText": ParagraphStyle(
                "TableText",
                parent=sample["BodyText"],
                fontName="Helvetica",
                fontSize=7.6,
                leading=9.8,
                alignment=TA_LEFT,
            ),
            "TableHeader": ParagraphStyle(
                "TableHeader",
                parent=sample["BodyText"],
                fontName="Helvetica-Bold",
                fontSize=7.6,
                leading=9.8,
                alignment=TA_CENTER,
            ),
        }
        return styles

    def build_pdf(
        self,
        plan_text: str,
        chat_title: str,
        user_email: str | None = None,
        *,
        document_label: str = "PLAN DE TRABAJO DE INVESTIGACION",
        filename_prefix: str = "plan_de_tesis",
        academic_profile: dict | None = None,
    ) -> tuple[bytes, str]:
        clean_plan_text = _clean_text(plan_text)
        title = _extract_title(clean_plan_text, chat_title)
        author = _extract_author(clean_plan_text, user_email)
        year = _extract_year(clean_plan_text)
        clean_document_label = (document_label or "DOCUMENTO ACADEMICO").strip().upper()

        buffer = io.BytesIO()
        document = ThesisPlanDocTemplate(buffer, document_label=clean_document_label)
        story = self._build_cover(
            title=title,
            author=author,
            year=year,
            document_label=clean_document_label,
            academic_profile=academic_profile,
        )
        story.append(PageBreak())
        story.extend(self._build_toc())
        story.append(PageBreak())
        story.extend(self._build_body(clean_plan_text))

        document.multiBuild(story)
        clean_prefix = _safe_filename(filename_prefix or "documento_academico")
        filename = f"{clean_prefix}_{_safe_filename(title)}.pdf"
        return buffer.getvalue(), filename

    def _build_cover(
        self,
        title: str,
        author: str,
        year: str,
        document_label: str,
        academic_profile: dict | None = None,
    ) -> list:
        faculty_name = (
            str((academic_profile or {}).get("faculty_name") or "").strip()
            or "FACULTAD PENDIENTE DE REGISTRO"
        )
        career_name = (
            str((academic_profile or {}).get("name") or "").strip()
            or "CARRERA PENDIENTE DE REGISTRO"
        )
        degree_label = f"TITULO PROFESIONAL EN {career_name.upper()}"
        return [
            Spacer(1, 0.8 * cm),
            Paragraph("UNIVERSIDAD PRIVADA DE TACNA", self.styles["cover_institution"]),
            Paragraph(_inline_markup(faculty_name.upper()), self.styles["cover_institution"]),
            Paragraph(_inline_markup(f"ESCUELA PROFESIONAL DE {career_name.upper()}"), self.styles["cover_institution"]),
            Spacer(1, 2.0 * cm),
            Paragraph(_inline_markup(document_label), self.styles["cover_label"]),
            Paragraph(f'"{_inline_markup(title.upper())}"', self.styles["cover_title"]),
            Paragraph("PARA OPTAR:", self.styles["cover_label"]),
            Paragraph(_inline_markup(degree_label), self.styles["cover_text"]),
            Spacer(1, 1.0 * cm),
            Paragraph("PRESENTADO POR:", self.styles["cover_label"]),
            Paragraph(_inline_markup(author), self.styles["cover_text"]),
            Spacer(1, 2.1 * cm),
            Paragraph("TACNA - PERU", self.styles["cover_text"]),
            Paragraph(year, self.styles["cover_text"]),
        ]

    def _build_toc(self) -> list:
        toc = TableOfContents()
        toc.levelStyles = [
            ParagraphStyle(
                "TocLevel1",
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                leftIndent=0,
                firstLineIndent=0,
                spaceBefore=5,
            ),
            ParagraphStyle(
                "TocLevel2",
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                leftIndent=16,
                firstLineIndent=0,
                spaceBefore=2,
            ),
        ]
        return [
            Paragraph("INDICE", self.styles["toc_title"]),
            toc,
        ]

    def _build_body(self, plan_text: str) -> list:
        flowables: list = []
        paragraph_buffer: list[str] = []
        table_buffer: list[str] = []

        def flush_paragraph() -> None:
            if not paragraph_buffer:
                return
            paragraph_text = " ".join(item.strip() for item in paragraph_buffer if item.strip())
            paragraph_buffer.clear()
            if paragraph_text:
                flowables.append(Paragraph(_inline_markup(paragraph_text), self.styles["BodyText"]))

        def flush_table() -> None:
            if not table_buffer:
                return
            rows = [_split_table_row(row) for row in table_buffer if not _is_table_separator(row)]
            table_buffer.clear()
            if rows:
                flowables.append(self._build_table(rows))
                flowables.append(Spacer(1, 8))

        for raw_line in plan_text.splitlines():
            line = raw_line.strip()

            if not line:
                flush_paragraph()
                flush_table()
                continue

            if re.fullmatch(r"-{3,}", line):
                flush_paragraph()
                flush_table()
                continue

            if _is_table_line(line):
                flush_paragraph()
                table_buffer.append(line)
                continue

            flush_table()

            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                flush_paragraph()
                heading_text = _plain_markdown(heading_match.group(2))
                flowables.append(Paragraph(_inline_markup(heading_text), self._style_for_heading(heading_text)))
                continue

            plain_line = _plain_markdown(line)
            if ROMAN_SECTION_PATTERN.match(plain_line):
                flush_paragraph()
                flowables.append(Paragraph(_inline_markup(plain_line), self.styles["BodyHeading1"]))
                continue

            if NUMERIC_SUBSECTION_PATTERN.match(plain_line):
                flush_paragraph()
                flowables.append(Paragraph(_inline_markup(plain_line), self.styles["BodyHeading2"]))
                continue

            bullet_match = re.match(r"^([-*])\s+(.+)$", line)
            numbered_match = re.match(r"^(\d+[.)])\s+(.+)$", line)
            if bullet_match:
                flush_paragraph()
                flowables.append(Paragraph(f"- {_inline_markup(bullet_match.group(2))}", self.styles["ListText"]))
                continue
            if numbered_match:
                flush_paragraph()
                flowables.append(
                    Paragraph(
                        f"{html_escape(numbered_match.group(1))} {_inline_markup(numbered_match.group(2))}",
                        self.styles["ListText"],
                    )
                )
                continue

            paragraph_buffer.append(line)

        flush_paragraph()
        flush_table()
        return flowables

    def _style_for_heading(self, heading_text: str) -> ParagraphStyle:
        if ROMAN_SECTION_PATTERN.match(heading_text):
            return self.styles["BodyHeading1"]
        if NUMERIC_SUBSECTION_PATTERN.match(heading_text):
            return self.styles["BodyHeading2"]
        return self.styles["BodyHeading1"]

    def _build_table(self, rows: list[list[str]]) -> Table:
        max_columns = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (max_columns - len(row)) for row in rows]
        column_widths = [USABLE_WIDTH / max_columns] * max_columns
        table_data = []

        for row_index, row in enumerate(normalized_rows):
            style_name = "TableHeader" if row_index == 0 else "TableText"
            table_data.append([
                Paragraph(_inline_markup(cell), self.styles[style_name])
                for cell in row
            ])

        table = Table(table_data, colWidths=column_widths, repeatRows=1, hAlign="LEFT", splitByRow=1)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#6f6f6f")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f3f6")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table


thesis_plan_pdf_service = ThesisPlanPdfService()
