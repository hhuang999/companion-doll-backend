"""Build a local, offline HTML reading edition and validate document assets."""

import argparse
import json
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "PROJECT_RESEARCH_AND_SYSTEM_DESIGN.md"
REPO = ROOT.parents[2]


def publish_pages(html):
    """Publish the full report at the site root and retain its previous URL."""
    destination = REPO / "docs/research-design"
    destination.mkdir(parents=True, exist_ok=True)

    def public_link(match):
        link = match.group(1)
        parsed = urlsplit(link)
        if parsed.scheme or not parsed.path or parsed.path.startswith("assets/"):
            return match.group(0)
        path = (ROOT / unquote(parsed.path)).resolve().relative_to(REPO)
        target = "https://github.com/hhuang999/companion-doll-backend/blob/main/"
        target += quote(path.as_posix())
        if parsed.fragment:
            target += "#" + parsed.fragment
        return f'href="{target}"'

    html = re.sub(r'href="([^"]+)"', public_link, html)
    homepage = re.sub(r'(href|src)="assets/', r'\1="research-design/assets/', html)
    homepage = homepage.replace(
        "</footer>",
        ' · <a href="showcase.html">交互展示</a>'
        ' · <a href="architecture-course/overview.html">交互架构图</a></footer>',
    )
    (REPO / "docs/index.html").write_text(homepage, encoding="utf-8")
    html = html.replace(
        '<p class="kicker">课程项目研究报告</p>',
        '<p class="kicker"><a href="../">项目首页</a> / 课程项目研究报告</p>',
    )
    (destination / "index.html").write_text(html, encoding="utf-8")
    for asset in (ROOT / "assets").iterdir():
        if asset.suffix in {".svg", ".png"}:
            target = destination / "assets" / asset.name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(asset, target)


def publish_readme(text):
    """Rebase Markdown links without changing the report's prose or structure."""

    def repository_link(match):
        parsed = urlsplit(match.group(2))
        if parsed.scheme or not parsed.path:
            return match.group(0)
        path = (ROOT / unquote(parsed.path)).resolve().relative_to(REPO)
        target = quote(path.as_posix())
        if parsed.fragment:
            target += "#" + parsed.fragment
        return f"{match.group(1)}({target})"

    text = re.sub(r"(!?\[[^\]]*\])\(([^)]+)\)", repository_link, text)
    navigation = (
        "[排版版网页（完整正文与章节目录）](https://hhuang999.github.io/companion-doll-backend/)"
        " · [交互展示](https://hhuang999.github.io/companion-doll-backend/showcase.html)"
        " · [交互架构图](https://hhuang999.github.io/companion-doll-backend/architecture-course/overview.html)"
        " · [安装与运行](ENGINEERING.md)\n\n"
    )
    text = text.replace("## 摘要\n", navigation + "## 摘要\n", 1)
    (REPO / "README.md").write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pages", action="store_true", help="Publish Pages homepage and root README"
    )
    args = parser.parse_args()
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
    if args.pages:
        publish_pages(html)
        publish_readme(text)
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
