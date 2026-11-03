# 课程升级源码架构图

五张图使用 Archify 生成，固定源码提交为 `38fb8cf`（完整SHA见各JSON）。对应课程内容、明确许可与输出闸门、有界协作、反馈记忆及小智实际实现。

| 视图 | 解释的问题 | 主要源码 |
| --- | --- | --- |
| [overview](overview.html) | 谁负责实时输入、安全、后台和输出 | core/api、cognition、memory、adapters |
| [content](content.html) | 研究如何进入策略选择、许可执行和反馈 | content/models/catalog/admission、state_machine、interaction |
| [collaboration](collaboration.html) | 独立评议、共享预算、一次修订与分产物发布 | scheduler、agents、budget、orchestrator |
| [memory](memory.html) | 来源、范围、更正、持久结束和迁移 | memory/service、store/cognition、migrate |
| [audio](audio.html) | 分句、下一句预取、固定接管、取消和测量 | xiaozhi/output、core/exercise、runtime |

JSON是可编辑源，HTML保持工具原样生成。`verification.json`含自动四关结果、固定提交和HTML摘要。五图均经过实际浏览器截图目视；内容图深浅主题和125%缩放可用。总图保留一处有桥接标记的交叉：扩大横向布局会使桌面文字过小，已恢复更易读方案；不宣称零交叉。

重新生成：

```text
node <已安装archify>/bin/archify.mjs finalize architecture docs/architecture-course/<name>.architecture.json docs/architecture-course/<name>.html --repo-root . --quality showcase --out-dir artifacts/diagrams/<新的目录> --json
```

`preview.png`是实际总图SVG区域的截图；README点击可进入项目站。旧v1和v2图集保留历史链接。发布方式见 [站点维护](../README.md)。
