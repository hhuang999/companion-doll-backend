# 架构图集维护与发布

GitHub Pages 从 `main` 分支的 `/docs` 发布。`index.html`、`atlas.css` 和 `atlas.js` 提供七个专题入口，`diagrams/*.html` 是 Archify 生成的独立交互图；`.nojekyll` 保持静态发布。

## 本版来源

源文件、提交绑定和验证记录位于 `.archify/architecture-modules-20261103-211600/`。每张图使用 `<slug>.candidate.json`，最终版本及检查记录以 `manifest.json` 为准。所有图固定到源码提交 `d24f38f0c065c2e9412c974afab5221d938b1316`。

## 更新步骤

1. 对照实际代码更新相关 candidate 的模块、关系、说明和来源引用；实现有变化时同步更新绑定提交。
2. 使用已安装的 Archify 运行 `finalize architecture <candidate> <html> --repo-root . --quality showcase --out-dir <新的检查目录> --json`。
3. 检查实际渲染，再将验证后的 HTML 原样复制到 `docs/diagrams/`，更新 manifest 中的 SHA-256 和检查记录路径。
4. 总图变化时，用图中“导出”生成新的 PNG，替换 `docs/assets/backend-architecture.png`。更新 README 的专题说明。
5. 检查七个入口、深链接、单独打开、主题切换、缩放、源码引用与导出；提交后推送 `main`，等待 Pages 部署成功。

只更新架构文档时无需调用模型或运行语音测试。不要手动改动 Archify 生成的 HTML；`docs/diagrams/*.html` 保留原始字节，便于与验证记录核对。
