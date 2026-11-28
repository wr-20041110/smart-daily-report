"""本地渲染 specs/uml/*.puml 为 PNG，输出到 docs/reports/figures/。

依赖：Java 运行时 + tools/lib/plantuml.jar（从 Maven Central 下载：
repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml/1.2024.8/plantuml-1.2024.8.jar）

用法：python tools/render_uml.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UML_DIR = ROOT / "specs" / "uml"
OUT_DIR = ROOT / "docs" / "reports" / "figures"
JAR = ROOT / "tools" / "lib" / "plantuml.jar"


def main() -> int:
    if not JAR.exists():
        print(f"未找到 {JAR}，请先下载 plantuml.jar（见本文件 docstring）")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pumls = sorted(UML_DIR.glob("*.puml"))
    result = subprocess.run(
        ["java", "-jar", str(JAR), *[str(p) for p in pumls], "-o", str(OUT_DIR)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    print(result.stdout.strip()[-500:] if result.stdout else result.stderr.strip()[-500:])
    ok = sum(1 for p in pumls if (OUT_DIR / f"{p.stem}.png").exists())
    print(f"完成：{ok}/{len(pumls)} 张渲染成功，输出目录 {OUT_DIR}")
    return 0 if ok == len(pumls) else 1


if __name__ == "__main__":
    sys.exit(main())
