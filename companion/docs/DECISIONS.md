# 实现决定

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
