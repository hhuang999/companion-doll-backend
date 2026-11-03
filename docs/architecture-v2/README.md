# v2 源码架构图

[打开图集](index.html)。每张 HTML 可以独立打开，支持缩放、关系追踪、深浅主题和导出；index 与 preview 作为本地图集入口和 README 预览。

源码依据固定于本地实现提交 `e3ef674820ee25c4873b4a9658a2a980060aa922`。使用 `link_mode: local-only`，没有发布本次提交或更新 GitHub Pages。图中边代表实际调用/控制责任，节点是 Python 模块职责而非微服务。

| 图 | 主要内容 | 编辑源 |
| --- | --- | --- |
| [实时与模块](overview.html) | 输入、Core、风险、策略、Talker、输出、后台、数据库 | overview.architecture.json |
| [协作与发布](collaboration.html) | 独立 Brief、确切版本评审、预算、Guard/CAS、部分提交 | collaboration.architecture.json |
| [关系记忆](memory.html) | 来源、范围、中文检索、更正、迁移、结束、清除 | memory.architecture.json |
| [语音流水](audio.html) | 有界预取、真实占用槽、取消、固定接管、回调与延迟 | audio.architecture.json |

使用本地 Archify 技能的 `bin/archify.mjs` 重建，例如在仓库根目录运行：

```powershell
node C:/Users/hhuan/.codex/skills/archify/bin/archify.mjs finalize architecture docs/architecture-v2/overview.architecture.json docs/architecture-v2/overview.html --repo-root . --quality showcase --out-dir artifacts/v2/diagram-manual --json
```

四张图均通过 validate、deliver、strict check 和 browser-check。总图额外执行 visual-check 并目视核对 1440×900 的深浅主题：布局调整后保留一处有清楚分色的风险线交叉，不表示两个通路相连；主路径、箭头和标签可辨。其余三图通过自动浏览器检查。原始检查回执保存在本地 `artifacts/v2/diagram-final-*.log` 和 `.archify/architecture-v2-20261103-231500/review-2/`。

架构图说明实现，不证明性能或正式材料合格；验收以 [VALIDATION](../../companion/docs/VALIDATION.md) 为准。
