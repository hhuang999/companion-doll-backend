# 项目研究与系统设计说明

完整材料面向课程老师、研究者与项目成员，按问题、证据、设计转译、内容、协作、记忆、控制及验证连续展开。

- [在线阅读新版说明（GitHub Pages 默认首页）](https://hhuang999.github.io/companion-doll-backend/)
- [仓库首页全文（Markdown）](../../../README.md)
- [阅读完整正文（Markdown）](PROJECT_RESEARCH_AND_SYSTEM_DESIGN.md)
- [打开排版阅读版（HTML）](index.html)：下载本目录后双击打开；支持目录、窄屏与浏览器打印，点击配图可查看原图。图片采用相对路径，分享时保留整个目录。
- [论证与图示计划](PLAN.md)
- [事实核对与交付检查](FACT_CHECK.md)
- [本轮编辑依据与结构调整](EDITORIAL_REVISION.md)

正文包含六张完整策略说明、三段短练习、三组贯穿案例、研究到实现的对应表，以及13张图。三张概念图实际由Codex图像生成工具制作，十张结构／数据图保存为可编辑SVG。合成场景与既有验收证据分别标注。

## 资产与修改

`assets/` 保存正文使用的13张图；`sources/IMAGE_PROMPTS.md` 保存三张生成图的提示词及检查记录。`sources/build_figures.py` 是九张结构图的布局、节点和箭头源，也是Matplotlib性能图的生成入口；`sources/performance.json` 保存图13使用的既有汇总值。图13的数据在构建脚本中声明，修改时同步其来源与正文表格。

`sources/build_document.py` 从Markdown生成HTML，并检查本地链接、图号顺序和SVG结构；`sources/reading.css` 维护阅读版排版。正文是唯一文字编辑源，修改后重新生成HTML。SVG保留文本与几何对象，可使用矢量编辑器进一步排版；保留构建脚本中的相同调整以便重建。

## 重建

在仓库根目录使用项目Python。文档依赖单独安装到忽略目录，不改变后端依赖：

```powershell
uv --cache-dir artifacts/research-design/uv-cache pip install --python .venv/Scripts/python.exe --target artifacts/research-design/deps -r companion/docs/research-design/sources/requirements.txt
$env:PYTHONPATH = (Join-Path (Get-Location) 'artifacts/research-design/deps')
./.venv/Scripts/python.exe companion/docs/research-design/sources/build_figures.py
./.venv/Scripts/python.exe companion/docs/research-design/sources/build_document.py
```

发布阅读版时，在最后一条命令加上 `--pages`，同步生成默认首页 `docs/index.html`、保留旧地址的 `docs/research-design/index.html`、13 张配图和根目录 `README.md`。根 README 保留完整正文并调整相对链接，顶部提供排版版网页入口；网页沿用本地版排版、目录和图注。工程文档链接指向 GitHub，图片和章节锚点留在站内。

交互展示保存在 `docs/showcase.html`，同时嵌入默认首页的完整报告之前，并提供单独打开链接。顶部入口模板为 `sources/home-intro.html`，首页专用布局为 `docs/assets/home.css`；`--pages` 会保留这一结构。独立阅读版和 `/research-design/` 仍只呈现报告。原根 README 的安装与运行内容保存在 `ENGINEERING.md`。正文、生成文件与配图一并提交到 `main` 后，沿用现有 GitHub Pages 发布。生成的根 README 和网页不单独编辑。

图源优先使用Windows微软雅黑；其他平台需要安装Noto Sans CJK SC。三张生成图作为已交付资产保留，重建不触发付费图像生成。HTML无外部脚本或字体依赖；外部文献与工程链接需访问相应来源。

## 版本与证据

文稿1.1，2026-11-04；八个正文部分、两份附录与参考资料，约1.59万中文字。当前实现基线`c33b50b`，内容`course-1.0`。文中工程、真实模型、质量与语音数据复用已登记批次，源码行为没有改变。文稿1.0保留在提交`0a79a5d`中。
