# 实现决定

## 研究驱动课程升级（2026-11-04，实施中）

最新授权与完成标准见 `autonomous-upgrade/TASK.md`，实施证据见该目录 `IMPLEMENTATION_STATUS.md`。以下 v1/v2 内容签字与固定卡片数量要求是历史决定，由本次课程范围准入替代；独立风险、许可、取消与来源规则继续适用。

策略目录先做目标、当前意愿、情绪/准备度、上下文排除、拒绝及使用次数过滤，再用可解释的中文关键词作有限排序。Planner 与 Critic 收到同一候选内容摘要，独立 Brief 仍不看候选。检索完整结果保存在 CognitiveJob 和已发布 SupportPlan 的 JSON 中，兼容旧记录缺省字段；不为附加 JSON 字段新增无用途 SQL 迁移。

内容使用语义 ID，并允许已知历史 S16；`enabled` 表示可追溯课程内容，和运行时 Critic 的 `approved` 分开。demo 要求来源核查、Codex 自动审查、内容 hash、逐项确定性行为与真实回放验收以及实测音频；不再硬编码 S03–S19 或虚构人工 reviewer。内容脚本/暂停和角色提示变化会让验收摘要失效；音频本机路径与实测时长不改变研究内容摘要，音频另作存在/实测校验。此阶段尚未启用新内容。

原 `test_config_has_every_stage_and_rejects_unreviewed_demo` 的错误消息断言改为缺课程内容清单，仍断言缺少准入证据时拒绝启动。不是删除旧安全检查。

接口核查：Aihubmix [TTS 文档](https://docs.aihubmix.com/cn/api/TTS)（2026-11-04 读取）FAQ 明确当前接口返回完整文件、不支持流式输出；正文“音频流”指二进制响应，不作为增量播放能力证明。优先优化句长、无效等待与现有预取，不将 `stream_to_file` 当成低首包增量合成。

## v2 实施决定（实现提交 e3ef674）

默认 development 已切到 `Cognition`；旧 Reasoner 不再作为发布执行器。`reasoner_runs` 保留历史，新的角色调用和最终事务结果写入 `agent_runs` / `cognitive_jobs`。Snapshot 是经代码卡片检查后的 SupportPlan 兼容投影；`active_support_plan_id` 与旧播放 `active_plan_id` 分开。

数据库采用事务化 v1→v2 迁移和 SQLite backup API；OS 文件锁覆盖迁移/活动 Core，进程退出自动释放，观察台仍只读直连。短事务支持 SAVEPOINT，使输入、明确控制、边界和状态可一起提交。后端锁序统一为用户锁→会话锁→Store。

后台编排与模型执行槽位分开；独立 Brief 使用专用有限执行器，后台 HTTP 客户端独立于实时客户端。无法中止的同步请求保留实际槽位，取消不伪造线程已退出。Token 预留采用可解释的保守估算（非 ASCII 字符按 2、ASCII 按 1/2，加消息开销），标 estimated；返回 provider usage 后结算，缺失不写零。实际保留 qwen-flash / qwen-plus，TTS 保留 gpt-4o-mini-tts / coral；没有开展新模型排名。

接口核查：[Aihubmix 结构化输出](https://docs.aihubmix.com/cn/api/Structured-Output) 说明存在自动降级，继续执行本地 Pydantic 和来源校验；[TTS](https://docs.aihubmix.com/cn/api/TTS) 的接口描述不作为增量音频实测证据，本次采用完整 WAV 合成加下一句有界预取；[Python SQLite backup](https://docs.python.org/3.10/library/sqlite3.html#sqlite3.Connection.backup) 用于 WAL 一致备份。

原测试 `test_old_reasoner_is_rejected_and_end_task_survives` 改查 v2 任务 cancelled：明确静默/会话结束主动取消旧协作，结束任务仍须 done，新会话不能被覆盖。没有取消原有许可、风险或恢复断言。

### 真实验收后的修正

- 原始 Planner 系统提示缺少 JSON 字样，Aihubmix 对 `json_object` 返回 400；补充明确输出格式，继续执行本地 schema 校验。Brief 的 evidence 和 Planner 的 response_guidance 单项也须使用数组，提示补充具体结构，未采用放宽 Pydantic 的隐式纠错。
- 历史 assistant 消息重新保留合法协议标签，避免模型模仿无标签正文；新增不从文字声称视觉观察、姓名仅简短确认、休息时收尾和明确 AI 关系边界。真实模型仍可能超时、过问或漏标签，输出护栏及失败状态保留。
- 后台压缩为有限历史、非播放反馈、必要记忆字段和卡片适用条件；去除 schema 的 title/description/default 描述，保留结构约束。一次 schema 修复共享预算，不能因为解析困难追加无限调用。
- 等待队列的在线测试由 25 秒改为 50 秒：v2 可串行执行策略和独立 memory 两个任务；单任务 20 秒硬 deadline 未改变。初轮 Talker 超时和旧观察窗口失败均保留，最终在线对话检查通过。
- 任务在实际执行开始捕获前驱提交后的版本，保留原排队年龄；普通输入不一律丢弃产物。发布前检查记忆更新后的依赖版本；输入/发布事务失败进入可诊断的受控状态。
- 反馈优先绑定已开始输出、该输出的策略和 offer；同一目标四轮两次明确失败触发 repeated_failure。server completed 与用户收益分开。策略 avoid 和 open_question 真正投影到 Talker，no_advice / no_repeat_offer 同时限制候选行动。
- 音频预取上限为下一句，TTS 两个真实占用槽；固定音频绕过动态合成。上游每句重置 packet_count，首包计时改为同一计数生命周期比较，补测 10 次均记录 sent；前 30 次缺测仍原样保留。
- 结束执行记录关联 retry_of / attempt；关闭超时停止新调度并保留已占用请求，durable end_tasks 由下次启动恢复。schema 诊断记录具体字段错误，角色运行记录实际提示 hash。

详细真实结果见 VALIDATION；没有将结构校验通过、服务端完成或单次性能改善等同于对话质量、设备播放或稳定达标。

## v1 历史决定（以下机制由 v2 保留或替代）

## 运行边界

采用一个独立 Python 包，以 CLI 与 OutputPort 驱动公共核心。SQLite 是会话和记忆的持久化来源；核心不引用小智模块，小智的可选依赖只在适配器实际运行时导入。一个数据库只运行一个核心进程，观察台独立只读查询。

## 模型与接口

当前 Aihubmix 账户已验证 qwen-flash 的流式文本、JSON 输出，qwen-plus 的后台分析，以及 gpt-4o-mini-tts / coral 的 WAV 合成。SDK 关闭自动重试；Reasoner 只对 JSON 格式失败在原预算内重试一次。结构化结果再经本地 Pydantic 和来源规则验证，不把 JSON 解析成功等同于提议有效。

SDK 懒加载资源在启动时初始化，避免将其开销计入首次模型请求。风险线程池与 Reasoner 分开；风险超时回退为 watch，迟到 high 仍可接管。模型和网络延迟仍高于文档目标，未降低验收门槛。

## 会话与取消

每次新输入固定 turn_id、generation、stage、snapshot。输出入口再次核验 generation；取消路径不等待模型返回 token。播放开始后激活许可，完成开场后提交 onboarding。风险回调独立于 respond 生成器，重复回调不重复接管、不重新打开已处理的同一风险事件。

Reasoner 每用户串行、跨用户并行。普通待运行任务合并，结束任务优先且写入数据库。发布时核验输入轮次、状态修订号和快照版本，再在同一事务中保存记忆、快照与运行记录。旧任务仍可报告过期，但不覆盖新状态。

正常收尾最多两个完成的回复轮，之后进入只陪伴；用户明确换题可以回到探索。规则与来源验证负责程序可检查的约束，输出文本质量另需真实模型检查。

## 内容

当前只保留设计文档声明的 S16 开发夹具。没有根据卡片编号补造其余研究内容。危机模板全部使用显式测试占位文本，三段练习标为 draft。development 可以验证机制；demo 要求 17 张正式卡、已审核危机模板和已审核且测量过的练习。

风险回归集由开发阶段编写，每类 40 条，包含理由、上下文、来源类别及待独立复核标记。结果只说明这一固定合成集的工程行为。组合策略与纯模型判断分开报告，超时和错误单列。

## 小智接入：四处扩展为六处

上游固定版本的 LLM 流循环只在迭代得到控制权后检查 client_abort；模型阻塞时无法通过此循环立即通知核心。上游还将唤醒词转成普通文本，核心仅凭内容不能可靠区分真正的唤醒控制事件。

因此在 I1–I4 外准备两处更改：`abortHandle.py` 调用 `interrupt_connection`，`listenMessageHandler.py` 显式传递 wake 来源。现有 I4 将普通 / wake / idle_end 注册为固定轮次，并绕开旧 chat/TTS 队列。新增 LLM provider 提供核心实例；Memory provider 幂等通知会话结束。

负责人已明确批准按六处补丁完成集成（2026-11-03）。统一补丁已应用到固定提交的本地 vendor 工作副本，重复安装检查已通过。完整 Python 3.10 环境已启动，并通过本机 WebSocket 客户端测试开场、回复、危机音频、打断、重连和真实 SenseVoice 输入；真机验收仍单列。

选用本地 Silero VAD 与 SenseVoiceSmall，Windows Opus 来自锁定 PyAV wheel。ASR 标签缺失时保留未知；无文字 Cry 使用明确的非语言事件说明通过上游空文本过滤。禁用唤醒音频缓存与旧意图路由，并使用最小上游 prompt 模板，避免旧角色和天气查询介入。核心配置和 SQLite 数据库为小智单独准备。

真实危机会话的结束分析曾返回 schema 不允许的 high。补充提示，要求 Reasoner 的 assessment 只输出 none / watch，并在文字摘要保留风险事实；high 继续由独立 RiskDetector 决定。原失败任务保留记录，通过显式重试成功完成。

## 音频完成语义

普通回复通过 Aihubmix 合成 WAV，再交给小智 Opus 编码与节奏发送器。固定危机和练习在启动前预生成，危机接管不临时调用 TTS。练习按实际音频时长与句后暂停校验 90 秒上限，暂停中也可以取消。

小智的 `_wait_for_audio_completion` 表示服务端发送队列排空与预缓冲等待；当前协议没有逐段设备播放 ACK。因此事件的完成是服务端估计，指标命名为 server_audio_start_ms，未冒充 device_first_audio_ms。真机验收必须独立录制实际声音和停止时刻。
# 研究驱动闭环升级补充（2026-11-04）

- 哭声触发安慰和情境重评，不能证明呼吸聚焦适用。练习有独立条件目录，明确指定的练习不能换成另一种；泛化行动许可转具体练习时重新说明并等同意。
- 策略执行ID/版本/步骤是服务端元数据，跟随实际输出与明确反馈。负反馈影响当前会话推荐；一次体验不改写永久偏好，发送完成不推断帮助。
- Talker默认只生成正文，状态、许可、表情由服务端拥有；旧标签仍解析并检查越权。省去首句前标签Token与等待，保留原输出闸门、分句和有界预取。跨轮问题预算与固定等候模板一起减少追问。
- 模型候选内部的no_topic_probe与开放问题冲突属于可修复问题：进入已有一次修订/最终复核，最终仍冲突不发布。练习投影只保留决策条件，完整协议在内容层；不通过增大任务预算掩盖上下文膨胀。
- 配置副本用发布v2资源基线作三方升级，预校验并备份，settings字段定制和音频路径保持。新增结构在既有JSON记录内可选，SQL版本保持2；未知数据库版本与事务迁移逻辑不变。
- 课程LAN接入新增每设备独立bearer凭据、服务端用户映射和请求头日志脱敏。保留六核心接入点，另加access.patch；既有匿名连接需升级凭据。明文WS用于受控课程LAN，公网需TLS终止；公开Pages不连接运行后端。设备ACK仍未实现。
- 固定音频资源由prepare_audio生成并绑定独立部署配置，验证文本/model/voice/文件hash/实测时长/停顿；生成资源不入公开仓库。课程内容准入仍要求真实回放回执，自动内容核查与工程验收分别记录。
# 2026-11-04：真实回放后的角色与测量修正

- 原 qwen-flash Analysis 在真实睡前场景遗漏bedtime、把安静环境错归no_private_space；qwen-plus同时承担Analysis/Critic又使长分析挤占20秒总deadline。线上Analysis去掉记忆候选的schema投影及不可达定义，保持持久契约兼容；明确边界由Core及时处理，长期整理由memory/end负责。最终待验配置使用qwen-plus Analysis/Planner、qwen-flash Brief/Critic，保持总deadline与任务预算。
- qwen-plus memory多次在20秒内未完成。小规模真实故障探针将memory/end换为Aihubmix gpt-4.1-mini，定点约2–4秒；Analysis/Planner不采用该探针中的替代配置，因为目标策略未执行。完整最终集独立验证，不能从探针速度推断质量通过。
- Aihubmix [结构化输出说明](https://docs.aihubmix.com/cn/api/Structured-Output)允许降级，因此保留本地Pydantic、来源和业务校验。实际qwen-plus的json_schema探针仍出现额外字段；gpt-4.1-mini能返回合法结构但也错判环境。结构合法不等于语义可靠，未据此关闭任何校验。
- 每任务共享一次schema修复。原memory每调用预约1800输出Token，首次产生少量无效输出后第二次仍预约1800会必然超1800总额；现在原子预约不超过剩余额度（不足128则拒绝），将实际预约值传给API并结算。调用、总Token、deadline限制不提高；新增测试验证修复后总额仍≤1800。
- 已有记忆只投影其memory_id、语义、范围和反馈归因，不把内部旧source_refs再次给模型当作当前原始输入。引用已有记忆必须用memory ID；新归因只用本次feedback实际提供的事件，减少重复候选和过期来源误引用。
- 小智探针必须等待整个输入的outputs终态及线路静默，再发下一轮。wake记录为control，固定high接管可能不走Talker的output_status；分别处理并断言危机固定原文。旧probe1“通过”被判为无效测量，修正probe3另存证据，没有用剩余普通音频冒充危机缓存。
- “分别/识别/个别”不再误触发“别”的交互边界。记录源与更正规则保持原样；普通叙述不能意外变成禁止追问。

### 课程最终回放中的边界与来源修复（2026-11-04）

最终集第二轮的自然倾诉 N01 暴露 `不想要办法` 被 ask 子串命中；加入明确拒绝匹配，让拒绝先于邀请。T04 的 `愿不愿意` 转述不再匹配 `不愿意`。保留直接撤回行为，新增业务状态断言。

T03 的流式闭引号曾成为单独输出，现忽略句后排版闭引号与无文字尾段，不等待下一 token 才发首句。Talker 明确区分计划和事实，输出护栏阻止无依据保证及已观察到的未许可建议句式。

记忆/结束模型即使结构正确，也可能把 output_id 当成 interaction_event ID。来源校验接入同一个角色调用的一次修复，仍共享调用、Token 与总 deadline；修复失败拒绝写入。没有放宽来源校验或扩大重试次数。端到端故障测试验证错误记忆不入库，合法修复后结束任务 done。

`quality-final1`、`quality-final2` 为保留的完整固定集执行。第二轮九个定向条目均执行；N08 的 idle_end 已移除 session，回放器应读取先前保存的 runtime 引用。此驱动错误已修复，真实补测与自然对话缺陷修复结果另记 `quality-final3` 及后续 evidence，不覆盖旧失败。

### 邀请被边界阻止后的输出与课程准入

最终N04暴露：Core撤销被边界阻止的邀请后，继续调用Talker会产生泛化建议。该分支现输出固定boundary_hold确认，不产生新行动；来源不明的边界仍按保守的current_topic处理。final6实际复测和152项离线检查通过，保留语言概括及模型超时限制。

课程回执course-release-1逐项关联六策略、三练习和危机文本的确定性/真实证据，绑定当前package_digest。所有实测音频准备后，实际部署Config(mode=demo)通过；这是合成/成年成员课程准入，不是人工或临床审核。首次机器仍须准备自己的音频，修改内容或提示词后回执过期。

### 2026-11-04：审查 P2 修复

- 具体练习邀请、同意后执行与中止恢复共用当轮适用性检查。已审核游标之后只有完整匹配的许可短句（且没有新情绪/非语言事件，普通Speech/NEUTRAL除外）时，可沿用原计划条件；任何新增情况都先阻止旧练习，并通过`exercise_recheck`进入已有有界deliberation。原TTL、控制版本、边界和拒绝约束仍有效。后台重评失败时不执行；重新符合条件后重新邀请并取得许可。恢复场景若被新评议排除，清除恢复位置，避免反复邀约。
- 原练习场景11在“刚才有声音”后立即邀请恢复的断言已更新：先等待重评，再邀请恢复，最后明确同意后执行。这是落实最新输入适用条件，不是移除中止恢复检查。
- 网站目录导出器读取指定提交的完整Git树，版本号、卡片/练习和来源保持一致。允许指定历史提交；不再把当前工作区内容标注成任意旧SHA。缺少清单或无效ref在覆盖公开JSON之前报错。
