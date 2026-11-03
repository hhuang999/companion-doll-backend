# 架构页面发布

GitHub Pages 从 `main` 分支的 `/docs` 目录发布，入口为 `index.html`。

- `index.html` 是 Archify 验证后的独立 HTML，保留完整交互功能。
- `assets/backend-architecture.png` 是 README 使用的预览图。
- `.nojekyll` 让 GitHub 直接发布静态文件。

本次页面的源文件和验证记录保存在 `.archify/architecture-public-20261103-210704/`。更新架构时，先更新该目录中的 `candidate.json` 并运行 Archify `finalize`，通过后将生成的 `architecture.html` 原样复制到 `docs/index.html`，重新生成预览图，再一同提交。

组件源码链接固定到已验证的 Git 提交，不随默认分支移动。仅修改页面时不需要运行模型或语音测试；需检查 README 图片、页面交互和源码链接。
