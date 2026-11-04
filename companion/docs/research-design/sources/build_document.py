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
        extension_configs={"toc": {"toc_depth": "2-3", "permalink": False}},
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
    css = """
    :root{color-scheme:light;--ink:#243538;--muted:#617073;--teal:#24746c;--paper:#fbfaf6}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.85 "Microsoft YaHei","Noto Sans CJK SC",sans-serif}
    nav{position:fixed;inset:0 auto 0 0;width:285px;padding:26px 24px;overflow:auto;border-right:1px solid #dce2df;background:#f1f3ee;font-size:13px;line-height:1.65}nav strong{display:block;font-size:18px;margin-bottom:16px}nav ul{list-style:none;padding-left:0}nav li{margin:7px 0}nav li ul{padding-left:13px;font-size:12px}nav a{text-decoration:none;color:#42575b}
    main{margin-left:285px;padding:60px clamp(24px,5vw,88px) 100px;max-width:1450px}h1{font-size:clamp(30px,3vw,43px);line-height:1.35;letter-spacing:-.02em;margin:0 0 22px}h2{font-size:28px;margin:70px 0 24px;padding-top:24px;border-top:2px solid #d1ded8}h3{font-size:22px;margin:36px 0 16px}p{margin:17px 0}a{color:var(--teal);text-underline-offset:3px}img{display:block;width:100%;height:auto;margin:30px 0 12px;border:1px solid #e0e4dc;border-radius:6px}p:has(>em:only-child){font-size:14px;color:var(--muted);line-height:1.75;margin-top:8px}p:has(>em:only-child) em{font-style:normal}code{font:0.86em Consolas,monospace;background:#edf0ea;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.7;margin:20px 0}th,td{border-bottom:1px solid #d6ded8;padding:12px 13px;text-align:left;vertical-align:top}th{background:#e9efea;color:#254f49}tr:nth-child(even){background:#f3f5f0}.table-scroll{overflow-x:auto}blockquote{margin:20px 0;border-left:3px solid var(--teal);padding:2px 20px;background:#edf3ee}.edition{font-size:12px;color:var(--muted);margin-bottom:28px}
    @media(max-width:1050px){nav{position:static;width:auto;max-height:250px;border-right:0;border-bottom:1px solid #dce2df;padding:20px}nav .toc>ul{columns:2}nav li ul{display:none}main{margin:0;padding:32px 24px 60px}}
    @media(max-width:600px){body{font-size:16px}main{padding:28px 18px}h2{font-size:25px}h3{font-size:20px}table{min-width:680px}nav .toc>ul{columns:1}img{border-radius:0}}
    @media print{@page{size:A4;margin:18mm 16mm}nav,.edition{display:none}body{background:white;font-size:10pt;line-height:1.65}main{margin:0;padding:0;max-width:none}h1{font-size:24pt}h2{font-size:17pt;margin-top:24pt;break-after:avoid}h3{font-size:13pt;break-after:avoid}img{max-height:225mm;object-fit:contain;break-inside:avoid}table{font-size:8pt;min-width:0}tr{break-inside:avoid}thead{display:table-header-group}a{color:inherit;text-decoration:none}p{orphans:3;widows:3}.table-scroll{overflow:visible}}
    """
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>情感陪伴玩偶 · 项目研究与系统设计说明</title><style>{css}</style></head><body><nav aria-label="目录"><strong>研究与系统设计</strong>{md.toc}</nav><main><div class="edition">本地阅读版 · 实现基线 c33b50b · <a href="PROJECT_RESEARCH_AND_SYSTEM_DESIGN.md">Markdown正文</a> · <a href="README.md">图源与核对记录</a></div>{body}</main></body></html>"""
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
