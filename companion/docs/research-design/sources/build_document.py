"""Build a local, offline HTML reading edition and validate document assets."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "PROJECT_RESEARCH_AND_SYSTEM_DESIGN.md"


def main():
    text = SOURCE.read_text(encoding="utf-8")
    errors = []
    links = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)
    for link in links:
        parsed = urlsplit(link)
        if not parsed.scheme and parsed.path and not (ROOT / unquote(parsed.path)).exists():
            errors.append(f"Missing local target: {link}")
    figures = re.findall(r"!\[图(\d+)[^\]]*\]\(([^)]+)\)", text)
    if [n for n, _ in figures] != [f"{i:02}" for i in range(1, 14)]:
        errors.append(f"Unexpected figure sequence: {figures}")
    for _, path in figures:
        if path.endswith(".svg"):
            tree = ET.parse(ROOT / path)
            if not tree.getroot().get("viewBox"):
                errors.append(f"SVG without viewBox: {path}")
    if errors:
        raise ValueError("\n".join(errors))
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2", "permalink": False}},
    )
    body = md.convert(text)
    body = re.sub(
        r'(<img\b[^>]*src="([^"]+)"[^>]*>)',
        r'<a href="\2" title="点击查看原图">\1</a>',
        body,
    )
    body = re.sub(
        r"(<table>.*?</table>)", r'<div class="table-scroll">\1</div>', body, flags=re.DOTALL
    )
    body = re.sub(
        r"<p>(<a[^>]+><img[^>]+></a>)</p>\s*<p><em>(图\d+.*?)</em></p>",
        r"<figure>\1<figcaption>\2</figcaption></figure>",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"(<h1[^>]*>.*?</h1>)\s*<p>(.*?)</p>",
        r'<header class="report-header"><p class="kicker">课程项目研究报告</p>\1<p class="subtitle">\2</p></header>',
        body,
        count=1,
        flags=re.DOTALL,
    )
    css = (ROOT / "sources/reading.css").read_text(encoding="utf-8")
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>情感陪伴玩偶的研究与系统设计</title><style>{css}</style></head><body><nav class="side-toc" aria-label="章节目录"><p>情感陪伴玩偶<br>研究与系统设计</p>{md.toc}</nav><details class="mobile-toc"><summary>章节目录</summary>{md.toc}</details><main><article>{body}</article><footer class="edition">文稿1.1 · 实现基线 c33b50b · <a href="PROJECT_RESEARCH_AND_SYSTEM_DESIGN.md">Markdown正文</a> · <a href="README.md">图源与核对记录</a></footer></main></body></html>"""
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(
        json.dumps(
            {
                "figures": len(figures),
                "generated_png": sum(p.endswith(".png") for _, p in figures),
                "editable_svg": sum(p.endswith(".svg") for _, p in figures),
                "local_and_external_links": len(links),
                "chinese_characters": len(re.findall(r"[\u4e00-\u9fff]", text)),
                "html": "index.html",
                "checks": "local links, ordered figures, SVG XML/viewBox",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
