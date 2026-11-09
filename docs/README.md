# 项目站点维护

GitHub Pages 从 `main:/docs` 发布，默认入口 [`index.html`](index.html) 顶部嵌入可操作的交互展示，提供单独打开链接；下方 `#research-report` 保留完整研究与系统设计说明、章节目录和全部 13 张配图。报告侧栏随正文滚动，不覆盖顶部展示；打印时仅输出报告。仓库根 README 同步呈现完整 Markdown 正文。

原交互展示保留在 [`showcase.html`](showcase.html)。`assets/project.css`、`project.js` 和 `project-data.json` 提供合成对话分支演示、四通路信号图、策略筛选、协议展开、累计延迟图与来源目录。静态页面不访问运行后端或 API key。设计约定见 [DESIGN.md](DESIGN.md)，界面验证见 [PAGES_VALIDATION.md](PAGES_VALIDATION.md)。

## 当前来源

首页展示区由 `companion/docs/research-design/sources/home-intro.html` 维护，布局在 `assets/home.css`。修改模板后执行下述 `build_document.py --pages` 重建，避免下次导出覆盖首页结构。展示页中的报告链接使用 `target="_top"` 跳到首页 `#research-report`，避免在嵌入区内重复打开首页。

正文、排版和图源维护在 [`companion/docs/research-design`](../companion/docs/research-design/README.md)，运行其中的 `sources/build_document.py --pages` 同步默认首页、根 README、旧地址 [`research-design/`](research-design/) 与配图；生成文件不单独编辑。旧地址仍显示全文并保留章节锚点。安装与运行说明移至 [`ENGINEERING.md`](../ENGINEERING.md)。

展示页架构部分的 `assets/layered-multiagent.png` 是经用户反馈重绘的 AI 辅助机制图，突出 L0–L3 内容职责、独立 Brief、Planner/Critic 修订复核和反馈记忆。L0–L3 是解释性分层，不是新增四个服务或固定执行阶段；六类策略也不是六个 Agent。图下提供可访问的文字说明和原图链接；具体源码仍以交互图为准。更新此图时同时核对说明、alt 文本、图片尺寸和窄屏阅读。

`architecture-course/` 保存五张架构图的可编辑 JSON 与原始生成 HTML；源码固定到实现提交，详见其中 README。`index-v2.html` / `architecture-v2/` 与 `index-v1.html` / `diagrams/` 为历史，不代表当前内容准入和模型配置。

## 更新步骤

对话演示使用 `project.js` 中的预设情境；更改时同时核对状态机与后台职责，保留“合成机制示意”说明。系统图选择与手机模块序列共用 `initSystemExplorer()` 的通路定义，完整 SVG 同步维护；后台候选经过 CAS 回到 Core，不直接绕过 Core 执行。P50/P90数值来自既有验证报告，累计节点作差只用于图形展示，不当作一条样本的分段实测。

两张原创概念图片及其小尺寸版本在 `assets/companion-daylight*.webp` 与 `assets/companion-touch*.webp`，精确提示词及生成方式见 [image-provenance.json](assets/image-provenance.json)。仅优化为WebP，不从参考品牌抓取产品图片。Manrope与Noto Sans SC字体自托管于 `assets/fonts/`；更新页面、脚本或目录中文时刷新子集，保留各自OFL许可，步骤见字体目录README。

1. 修改代码和内容后完成检查并提交。运行 `.venv/Scripts/python.exe scripts/build_project_site.py --revision HEAD`，从指定提交的 Git tree 读取来源、策略和练习，再导出公开JSON；工作区未提交的修改和新增文件不会混入。历史提交须包含内容清单，缺失资源或无效提交会在写入前失败并保留原JSON。仅对已提交的内容固定引用。
2. 修改相应 `architecture-course/*.architecture.json`，更新具体源码依据及固定提交；用 Archify `finalize architecture <JSON> <HTML> --repo-root . --quality showcase --out-dir <新的本地证据目录> --json`。
3. 核查实际渲染、节点、箭头、缩放、主题和源码链接。不得手改生成HTML。总图预览来自实际渲染图区域截图。
4. 启动 `.venv/Scripts/python.exe -m http.server 8765 --bind 127.0.0.1 --directory docs`。用 Ego 浏览器检查桌面/窄屏、键盘、筛选、长内容、资源和控制台。维护 `DESIGN.md` 与验证报告。
5. 检查提交不含私有数据，正常推送/集成 main，等待 Pages workflow 完成，并访问线上URL核对新内容。

公开汇总来源于合成回放。原始数据库、完整运行日志、客户端凭据与音频留在忽略的 `artifacts/`、`data/`。
