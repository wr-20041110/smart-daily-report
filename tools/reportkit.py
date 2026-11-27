"""Word 报告生成框架（课程排版要求：A4、目录自动生成、三级编号、图表统一编号并引用）。

用法：
    from tools.reportkit import Report, T
    r = Report("docs/reports/01-业务调研报告.docx", "业务调研报告", "智能日报生成器项目组")
    r.h1("第1章 调研大纲"); r.p(...); r.table(...); r.fig("图1-1 用例图", "specs/uml/usecase.puml")
    r.save()
"""

from __future__ import annotations

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


def _set_cell_bg(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def _set_east_asia(run, name: str) -> None:
    """为 run 设置中文字体（确保 rPr/rFonts 节点存在）。"""
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), name)


class Report:
    """一份 Word 报告：A4、宋体正文、标题层级、表格与图编号。"""

    def __init__(self, path: str, title: str, team: str = "智能日报生成器项目组") -> None:
        self.doc = Document()
        self.path = path
        self.title = title
        self.team = team
        self._table_no = 0
        self._fig_no = 0
        self._setup_page()
        self._setup_styles()
        self._title_page()
        self._toc()

    # ---- 版式与样式 ----

    def _setup_page(self) -> None:
        sec = self.doc.sections[0]
        sec.orientation = WD_ORIENT.PORTRAIT
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.6)
        sec.top_margin = sec.bottom_margin = Cm(2.8)

    def _setup_styles(self) -> None:
        normal = self.doc.styles["Normal"]
        normal.font.name = "Times New Roman"
        normal.font.size = Pt(12)
        normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
        normal.paragraph_format.line_spacing = 1.5
        for name, size in (("Heading 1", 16), ("Heading 2", 14), ("Heading 3", 12.5)):
            st = self.doc.styles[name]
            st.font.name = "Times New Roman"
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.color.rgb = None
            st.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "黑体")

    def _title_page(self) -> None:
        for _ in range(5):
            self.doc.add_paragraph()
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(self.title)
        run.font.size = Pt(26)
        run.font.bold = True
        run.font.name = "Times New Roman"
        _set_east_asia(run, "黑体")
        p2 = self.doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r2 = p2.add_run("软件工程职业技能实践课程设计")
        r2.font.size = Pt(16)
        _set_east_asia(r2, "黑体")
        self.doc.add_paragraph()
        p3 = self.doc.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r3 = p3.add_run(f"项目组：{self.team}\n成员：王然、咸哲、王峻羽\n2026 年 12 月")
        r3.font.size = Pt(14)
        _set_east_asia(r3, "宋体")
        self.doc.add_page_break()

    def _toc(self) -> None:
        p = self.doc.add_paragraph()
        run = p.add_run()
        fld_char = OxmlElement("w:fldChar")
        fld_char.set(qn("w:fldCharType"), "begin")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = 'TOC \\o "1-3" \\h \\z \\u'
        fld_char2 = OxmlElement("w:fldChar")
        fld_char2.set(qn("w:fldCharType"), "separate")
        t = OxmlElement("w:t")
        t.text = "（目录：请在 Word 中全选后按 F9 更新域生成）"
        fld_char3 = OxmlElement("w:fldChar")
        fld_char3.set(qn("w:fldCharType"), "end")
        run._r.append(fld_char)
        run._r.append(instr)
        run._r.append(fld_char2)
        run._r.append(t)
        run._r.append(fld_char3)
        self.doc.add_page_break()

    # ---- 内容 API ----

    def h1(self, text: str) -> None:
        self.doc.add_heading(text, level=1)

    def h2(self, text: str) -> None:
        self.doc.add_heading(text, level=2)

    def h3(self, text: str) -> None:
        self.doc.add_heading(text, level=3)

    def p(self, text: str, bold: bool = False, indent: bool = True) -> None:
        para = self.doc.add_paragraph()
        if indent:
            para.paragraph_format.first_line_indent = Pt(24)
        run = para.add_run(text)
        run.font.bold = bold

    def bullet(self, text: str) -> None:
        self.doc.add_paragraph(text, style="List Bullet")

    def table(self, caption: str, headers: list[str], rows: list[list[str]]) -> None:
        self._table_no += 1
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cap.add_run(f"表{self._table_no} {caption}")
        run.font.bold = True
        run.font.size = Pt(10.5)
        t = self.doc.add_table(rows=1 + len(rows), cols=len(headers))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(headers):
            cell = t.rows[0].cells[j]
            cell.text = h
            _set_cell_bg(cell, "D9E2F3")
            for para in cell.paragraphs:
                for r in para.runs:
                    r.font.bold = True
                    r.font.size = Pt(10.5)
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                cell = t.rows[i + 1].cells[j]
                cell.text = str(val)
                for para in cell.paragraphs:
                    for r in para.runs:
                        r.font.size = Pt(10.5)
        self.doc.add_paragraph()

    def fig(self, caption: str, source_note: str) -> None:
        """图占位：标题 + 来源说明（UML 图为 PlantUML 工具绘制，源文件在 specs/uml/）。"""
        self._fig_no += 1
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cap.add_run(f"图{self._fig_no} {caption}")
        run.font.bold = True
        run.font.size = Pt(10.5)
        note = self.doc.add_paragraph()
        note.alignment = WD_ALIGN_PARAGRAPH.CENTER
        nr = note.add_run(f"（{source_note}；渲染图片请用 PlantUML 导出后替换本占位）")
        nr.font.size = Pt(9)
        nr.font.italic = True
        self.doc.add_paragraph()

    def save(self) -> str:
        self.doc.save(self.path)
        return self.path


def T(*cells: str) -> list[str]:
    """表格行构造便捷函数。"""
    return list(cells)
