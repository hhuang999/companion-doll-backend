# 项目研究与系统设计说明

完整材料面向课程老师、研究者与项目成员，按问题、证据、设计转译、内容、协作、记忆、控制及验证连续展开。

- [阅读完整正文（Markdown）](PROJECT_RESEARCH_AND_SYSTEM_DESIGN.md)
- [打开排版阅读版（HTML）](index.html)：下载本目录后双击打开；支持目录、窄屏与浏览器打印，点击配图可查看原图。图片采用相对路径，分享时保留整个目录。
- [论证与图示计划](PLAN.md)
- [事实核对与交付检查](FACT_CHECK.md)

正文包含六张完整策略说明、三段短练习、三组贯穿案例、研究到实现的对应表，以及13张图。三张概念图实际由Codex图像生成工具制作，十张结构／数据图保存为可编辑SVG。合成场景与既有验收证据分别标注。

## 资产与修改

`assets/` 保存正文使用的13张图；`sources/IMAGE_PROMPTS.md` 保存三张生成图的提示词及检查记录。`sources/build_figures.py` 是九张结构图的布局、节点和箭头源，也是Matplotlib性能图的生成入口；`sources/performance.json` 保存图13使用的既有汇总值。图13的数据在构建脚本中声明，修改时同步其来源与正文表格。

`sources/build_document.py` 从Markdown生成HTML，并检查本地链接、图号顺序和SVG结构。正文是唯一文字编辑源，修改后重新生成HTML。SVG保留文本与几何对象，可使用矢量编辑器进一步排版；保留构建脚本中的相同调整以便重建。

## 重建

在仓库根目录使用项目Python。文档依赖单独安装到忽略目录，不改变后端依赖：

```powershell
uv --cache-dir artifacts/research-design/uv-cache pip install --python .venv/Scripts/python.exe --target artifacts/research-design/deps -r companion/docs/research-design/sources/requirements.txt
$env:PYTHONPATH = (Join-Path (Get-Location) 'artifacts/research-design/deps')
./.venv/Scripts/python.exe companion/docs/research-design/sources/build_figures.py
./.venv/Scripts/python.exe companion/docs/research-design/sources/build_document.py
```

图源优先使用Windows微软雅黑；其他平台需要安装Noto Sans CJK SC。三张生成图作为已交付资产保留，重建不触发付费图像生成。HTML无外部脚本或字体依赖；外部文献与工程链接需访问相应来源。

## 版本与证据

2026-11-04，当前实现基线`c33b50b`，内容`course-1.0`。文中工程、真实模型、质量与语音数据复用已登记批次，本任务新增的是设计成稿、图资产和文档检查。源码行为没有改变。
