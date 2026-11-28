"""报告排版后处理（在已生成的 docx 上原地修改，保留人工改写内容）：

1. 每一章（Heading 1）另起一页（除第一章外设置 page_break_before）；
2. 封面与目录不显示页码；从第一章开始显示页码，且页码从 1 起算；
3. 不改动任何字体与样式。

用法：python tools/format_reports.py
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

REPORTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "reports"


def format_one(path: Path) -> None:
    doc = Document(str(path))
    h1_paras = [p for p in doc.paragraphs if p.style.name == "Heading 1"]
    if not h1_paras:
        print(f"  {path.name}: 无章节标题，跳过")
        return

    first = h1_paras[0]

    # 1) 在第一章标题前插入分节符（新页），封面+目录为第 1 节（无页码）
    prev_p = first._p.getprevious()
    if prev_p is None:
        print(f"  {path.name}: 第一章前无段落，跳过")
        return
    # 若前一页段落带分页符，删除分页符 run，避免与分节符叠加产生空白页
    for run in prev_p.findall(qn("w:r")):
        if run.find(qn("w:br")) is not None:
            prev_p.remove(run)
    sect_pr = copy.deepcopy(doc.element.body.sectPr)
    prev_p.get_or_add_pPr().append(sect_pr)

    # 2) 第二章起每章另起一页（不动字体，只设段前分页）
    for h1 in h1_paras[1:]:
        h1.paragraph_format.page_break_before = True

    # 3) 第 2 节（第一章起）页脚：居中页码，从 1 开始
    sec2 = doc.sections[0]  # body 级 sectPr = 最后一节（章节部分）
    sec2.footer.is_linked_to_previous = False
    footer_p = sec2.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_p.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)
    pg_num = OxmlElement("w:pgNumType")
    pg_num.set(qn("w:start"), "1")
    sec2._sectPr.append(pg_num)

    doc.save(str(path))
    print(f"  {path.name}: 排版完成（{len(h1_paras)} 章，每章另起一页，第一章起编页码）")


def main() -> int:
    files = sorted(REPORTS_DIR.glob("*.docx"))
    for f in files:
        format_one(f)
    print(f"共处理 {len(files)} 份报告")
    return 0


if __name__ == "__main__":
    sys.exit(main())
