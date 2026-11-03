# 正式材料接入

工程默认允许待审核材料用于本地机制测试。切换 demo 前按以下顺序准备内容。

1. 根据《研究链 v3》逐张核对 S03–S19 的名称、适用条件、排除条件、步骤、禁用说法与引用。在 `cards/` 中按 ID 放置 YAML，标为 `approved`，保留真实来源。S16 当前的 `fixture` 需要替换成核对后的正式内容。
2. 在 `crisis.yaml` 填入审核后的开场、后续回应、援助信息、结束话术以及 reviewer / reviewed_at / version，完成审核后设 `approved: true`。模板选择和每三轮援助提醒由代码控制。
3. 核对三段练习，设为 `approved`。为每句填写相对于配置目录的 `audio_path` 和实测 `audio_duration_s`，加上 `pause_s` 后总时长不超过 90 秒。代码会拒绝缺失音频和不合格时长。
4. 运行 `companion.tools.prepare_audio` 重新生成固定音频。缓存键包含文字、TTS 模型和 voice，内容变化不会复用旧音频。
5. 使用 `--mode demo --config-dir <目录>` 检查配置，再运行真实模型剧本和真机练习 / 危机联调。

正式卡片的基本字段见 `config/cards/S16.yaml`。`requires_permission` 只接受 true；所有行动都经过明确同意。`targets.pressure_types` 与 `targets.pathways` 为 OR 匹配，空的一侧不会自动匹配所有用户。情绪排除条件和每会话次数在验证与进入行动时复核。

当前自动检查能核验格式、ID、审批字段、来源轮次、状态约束和音频文件。它不能判断研究内容是否忠实、话术是否适合真实学生，也不会自动生成审核人的签名。


## v2 接入状态

v2 Planner / Critic 可读取卡片适用条件和排除项；最终行动仍由 Validator 和明确许可决定。三角色不得自行把 draft 改为 approved。当前仍仅有 S16 开发夹具，正式 S03–S19、审核危机文本和练习需要负责人提供。质量回放使用 `config/v2_scenarios.yaml` 的预固定合成文本；它们是工程验收输入，不是新的研究材料或内容审批。
