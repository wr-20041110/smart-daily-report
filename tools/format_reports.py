"""报告排版后处理（在已生成的 docx 上原地修改，保留人工改写内容；幂等可重复运行）：

1. 每一章（Heading 1）另起一页（除第一章外设置 page_break_before）；
2. 封面与目录（第 1 节）不显示页码；第一章起（第 2 节）页脚居中页码，从 1 起算；
3. 不改动任何字体与样式。

关键点：段落级 sectPr = 第 1 节（封面+目录）；body 级 sectPr = 第 2 节（章节正文）。
页脚引用与页码起始必须放在 body 级 sectPr 上（本脚本按此搬移，幂等）。

用法：python tools/format_reports.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

REPORTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "reports"


def format_one(path: Path) -> None:
    doc = Document(str(path))
    body = doc.element.body
    h1_paras = [p for p in doc.paragraphs if p.style.name == "Heading 1"]
    if not h1_paras:
        print(f"  {path.name}: 无章节标题，跳过")
        return

    # 1) 第一章标题前必须有分节符（第 1 节 = 封面+目录）；缺少时补建
    first = h1_paras[0]
    prev_p = first._p.getprevious()
    par_sects = body.findall(".//" + qn("w:pPr") + "/" + qn("w:sectPr"))
    if prev_p is not None and len(par_sects) == 0:
        # 首次处理：在第一章前段落插入分节符（干净副本，不含页脚）
        import copy

        from docx.oxml import OxmlElement

        sect_pr = copy.deepcopy(body.sectPr)
        prev_p.get_or_add_pPr().append(sect_pr)
        par_sects = body.findall(".//" + qn("w:pPr") + "/" + qn("w:sectPr"))
        print(f"  {path.name}: 已插入分节符")
    if not par_sects:
        print(f"  {path.name}: 未找到分节符，跳过")
        return

    # 2) 页脚引用与页码起始必须属于 body 级 sectPr（第 2 节）
    par_sect = par_sects[0]
    body_sect = body.sectPr
    fref = par_sect.find(qn("w:footerReference"))
    pg_num = par_sect.find(qn("w:pgNumType"))
    if fref is not None:
        par_sect.remove(fref)
        if body_sect.find(qn("w:footerReference")) is None:
            body_sect.insert(0, fref)  # footerReference 必须位于 pgSz 之前
    if pg_num is not None:
        par_sect.remove(pg_num)
        if body_sect.find(qn("w:pgNumType")) is None:
            cols = body_sect.find(qn("w:cols"))
            if cols is not None:
                cols.addprevious(pg_num)  # pgNumType 必须位于 cols 之前
            else:
                body_sect.append(pg_num)

    # 3) 第二章起每章另起一页（不动字体）
    for h1 in h1_paras[1:]:
        h1.paragraph_format.page_break_before = True

    doc.save(str(path))
    print(f"  {path.name}: 排版完成（{len(h1_paras)} 章，页码自第一章起）")


def main() -> int:
    files = sorted(REPORTS_DIR.glob("*.docx"))
    for f in files:
        format_one(f)
    print(f"共处理 {len(files)} 份报告")
    return 0


if __name__ == "__main__":
    sys.exit(main())
