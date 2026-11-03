# 项目站点维护

GitHub Pages 从 `main:/docs` 发布，入口是 `index.html`。`assets/project.css`、`project.js` 和 `project-data.json` 提供中文项目说明、条件筛选、协议展开和来源目录。静态页面不访问运行后端或 API key。

## 当前来源

`architecture-course/` 保存五张架构图的可编辑 JSON 与原始生成 HTML；源码固定到实现提交，详见其中 README。`index-v2.html` / `architecture-v2/` 与 `index-v1.html` / `diagrams/` 为历史，不代表当前内容准入和模型配置。

## 更新步骤

1. 修改代码和内容后完成检查并提交。运行 `.venv/Scripts/python.exe scripts/build_project_site.py --revision HEAD`，将当前内容映射导出到公开JSON。仅对已提交的内容固定引用。
2. 修改相应 `architecture-course/*.architecture.json`，更新具体源码依据及固定提交；用 Archify `finalize architecture <JSON> <HTML> --repo-root . --quality showcase --out-dir <新的本地证据目录> --json`。
3. 核查实际渲染、节点、箭头、缩放、主题和源码链接。不得手改生成HTML。总图预览来自实际渲染图区域截图。
4. 启动 `.venv/Scripts/python.exe -m http.server 8765 --bind 127.0.0.1 --directory docs`。用 Ego 浏览器检查桌面/窄屏、键盘、筛选、长内容、资源和控制台。维护 `DESIGN.md` 与验证报告。
5. 检查提交不含私有数据，正常推送/集成 main，等待 Pages workflow 完成，并访问线上URL核对新内容。

公开汇总来源于合成回放。原始数据库、完整运行日志、客户端凭据与音频留在忽略的 `artifacts/`、`data/`。
