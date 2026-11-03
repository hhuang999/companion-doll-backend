# 研究驱动升级：持续实施状态

更新时间：2026-11-04（Asia/Singapore）。权威任务：[TASK.md](TASK.md)。状态：进行中。
分支 `codex/research-support-upgrade`；起点 `3cb20bc8b47ef15924ca1a3c6557951a5680cd0c`。
最近完成提交：`319d59e` 内容契约/检索；`272e825` 六类研究支持与逐策略执行。后续闭环升级已通过检查，正整理提交。
本文件是跨上下文继续工作的入口；未列证据的项目不算完成。

## 已核实基线

- START / TASK / CONTEXT / 研究链原始副本已读取；没有项目级 AGENTS.md，沿用用户提供的全局约定。
- 既有跟踪文件干净，历史 `.archify`、旧文稿与本次任务包未跟踪；保留，不全量 add。
- 现有 `.venv/Scripts/python.exe`：Python 3.10.20。
- `./scripts/run.ps1 test`：Ruff / format 通过，96 passed、3 deselected；`artifacts/autonomous-upgrade/baseline.txt`。
- 当前主路径为 v2 Cognition，内容只有 S16 fixture；demo 仍硬编码 S03–S19 / 人工 reviewer。
- 研究链的 A 线全文未提供；将根据核实资料重建并记录映射，不补造旧编号含义。
- 最新 TASK 替代旧内容签字、固定数量与必须本任务真机验收限制；其余 v2 安全/并发约束保留。

## 需求—实现—证据矩阵

| ID / TASK | 交付与完成证据 | 当前状态 / 位置 |
| --- | --- | --- |
| U01 §3、9.1 | 基线、独立分支、持久状态、证据索引 | 基线通过；本文件 |
| U02 §4.1 | 来源逐条核查、反例、适配和读取范围 | 16 个关键来源记录已核对，主张/限制/策略映射完成；research/EVIDENCE_REVIEW.md；按实现空白继续补充 |
| U03 §4.2–4.3 | 五压力/四路径/求助障碍覆盖、筛选与排除、历史映射 | 六类支持已编写，选择/排除/合并见 STRATEGY_DESIGN.md；真实适配继续验证 |
| U04 §5.1、7 | 可版本化内容包、筛选、适用/排除、可追溯准入 | content/models、catalog、admission 接入；content_manifest 含16来源/10条核查，acceptance=null，demo尚不放行 |
| U05 §5.2、6 | Analysis/Planner/Brief/Critic/Talker 真正读取并执行策略；默认路径 | 默认 Cognition 筛选并给 Planner/Critic 同一摘要，Brief隔离；Talker只读当前一步，按实际步数结束；真实协议已调试 |
| U06 §6、7 | 许可/撤回/切换/去重/退出、短练习及固定危机接管 | 三练习协议/过滤/指定目标/单独许可/拒绝/取消接通；哭声改为安慰与重评；真实睡前选择修复后待复测 |
| U07 §5.2、6 | 反馈归因、记忆、结束恢复与跨会话跟进闭环 | SupportReference贯通policy/output/event/memory；明确反馈校验实际事件；负反馈只阻止本会话重复；最终跨会话live仍待 |
| U08 §6 | 迁移、幂等、备份、配置副本保留定制、wheel 资源 | upgrade_config三方默认值合并、预校验/备份/幂等；实际data/xiaozhi-config已升级并保持settings定制；wheel待 |
| U09 §7、9.4 | 固定音频生成与实测≤90s、版本缓存、取消 | 24音频准备并绑定；睡前29.9s/呼吸36.25s/外部注意33.7s（含停顿）；脚本/声音/hash/停顿校验；设备链路待 |
| U10 §8 | 小智身份/鉴权、协议/错误/超时、模拟客户端、交接包 | 新access.patch保留六核心hook，独立凭据映射与请求头日志脱敏；身份伪造/轮换/禁用测试通过；实际服务启动检查中 |
| U11 §9.2 | 全条目适用/排除/拒绝/退出/反馈；故障并发回归 | 六策略和三练习逐项执行；完整回归141 passed /3 deselected，closed-loop5.txt；最终验收集待 |
| U12 §9.3 | 固定最终集≥12段、与调试集分开；每策略真实链路+自然选择；逐段审读 | 待实现并验证 |
| U13 §9.4 | CLI/观察台/WS/Opus/ASR/动态TTS/固定接管实际运行 | 待验证 |
| U14 §9.5 | 合理优化、最终≥30动态语音尝试、全部分母与分段P50/P90/Token | 待实现并验证 |
| U15 §10 | 完整中文项目站、策略交互、源码图、桌面/窄屏/键盘/资源检查 | 待实现并验证 |
| U16 §11 | 文档、展示脚本、本地提交、GitHub正常集成、Pages线上核验 | 待完成 |

## 实施决定

1. 保持当前模块化单体与有界 Agent 协议；研究资料离线核查并压缩成可执行内容，在线不逐轮联网搜索。
2. 课程内容准入将明确区分来源核查、自动审查、工程回放与适用范围；不能将机器核查记为人工/临床审核。
3. 新策略使用语义化 ID，保留已知 S16 映射与旧记录可读性；不猜测缺失 S03–S19 的原义。

## 进行中的工作与下一步

- research 技能要求的子任务 `research_evidence` 已完成，仅写 EVIDENCE_REVIEW.md；主线程已阅读其结果。
- 主线程：检查当前内容/校验/Agent/状态路径，先完成可运行的内容检索与执行纵向链路，再补全内容和真实验收。
- 首条纵向链路：6 项新行为检查通过；完整回归 102 passed / 3 deselected（`content-regression2.txt`）。首轮 Ruff 因调用未指定项目 config 的 import 分类失败，已按正式入口修正并保留日志；不是业务失败。
- 增加完整准入与六类失败回归后：**109 passed / 3 deselected**，Ruff / format 通过（`content-regression3.txt`）。正向准入使用测试临时目录中的显式合成回执，不是生产内容已验收。
- 检索结果在任务失败时也保留，模型不得指定被过滤卡；启用内容缺核查或 hash 过期会拒绝启动。
- 第一阶段提交 `319d59e`：研究、任务入口、内容契约与准入/检索，109项离线通过。
- 六类支持已写入默认配置：S16（具体一步）、kind_self_talk、safe_communication、safe_support、values_exploration、worry_parking。三段短练习改为自然呼吸/外部定位/睡前暂停，危机占位替换为课程模拟固定文本。自动内容核查已记录；音频/正式回放未完成，demo仍拒绝。
- `content-pack1.txt` 8 failed / 7 errors：新内容改变旧夹具前提，以及摘要膨胀超预算；压缩重复字段、测试显式给readiness/目标侧后，`content-pack2.txt`仅剩按列表首项索引错误；按ID断言修复。未增加运行预算。
- `content-pack3.txt`、`content-pack4.txt`：121 passed /3 deselected，Ruff/format通过。后续新增危机/练习启用状态的hash检查，25项内容定点通过。
- `content-pack5.txt`：补充检查后的正式入口再次121 passed /3 deselected，Ruff/format通过。最后澄清卡片not_when：未获执行许可不等于不能生成邀请候选，执行仍要求明确同意；同步内容核查hash。
- 远端 main / codex/backend-v2 均为起点提交；Pages 实查 built、main:/docs。沙箱内 gh 404，正常凭据上下文查询成功。
- 官方 TTS 文档明确返回完整音频文件，下一轮重点优化实时输出协议与句长，保留有界预取。
- 已告知并执行三轮真实调试（旧Q06各3轮），53条后台角色记录；`live-debug1/2/3/report.json`与对应log均保留。debug1有4条Critic schema_error；debug2结构全部成功但有评审业务拒绝/分析强度过判；debug3为21角色completed，候选S16实际发布，但用户下一轮直接中止，尚未证明真实执行。debug3风险2次超时回退watch，未改风险阈值。结束任务均done。这些是调试集，不计最终固定验收。
- 还未推送本轮任何内容；TASK 已授权最终 GitHub / Pages 发布。

## 继续工作时的具体入口

1. 六类支持已编写，见STRATEGY_DESIGN。`artifacts/autonomous-upgrade/build_content.py`是一次性写入辅助脚本，配置YAML为实际可编辑源；后续修改配置应同步review hash，勿盲目重跑覆盖新修改。当前manifest acceptance=null。
2. Talker已只投影当步并限制实际步数。继续优化跨轮问句预算、标签首行开销和短句；现有Core掌握状态，考虑正文协议兼容旧标签以消除missing_tag，不削弱许可/输出闸门。
3. 优先补全策略版本→当轮→反馈→支持经历归因；练习仍只有ID列表提供给Planner/Critic、实际选择硬编码breathing_60s，需内容协议与真正选择/排除。
4. 准入目前已检查逐项覆盖、prompt/content digest、音频文件实际时长；固定音频文本/缓存绑定和准备工具需补齐。默认 demo 待实际完整内容及真实验收后才能通过。
5. 阅读 EVIDENCE_REVIEW 的研究限制；不把六周/八周或人工干预效果归给短语音。Aihubmix 不支持增量 TTS 的官方证据已记 DECISIONS。
6. 援助资源工具返回了不匹配目标中国大陆的日本地区结果，未采用其号码。教育部学校支持/隐私官方页面搜索存在，但打开遇重定向/超时，尚未将摘要当全文核查。可重试官方来源；不要凭记忆写危机热线。
7. 本轮已执行上述付费模型调试，尚未运行新固定音频、最终质量集、语音30次、看板、wheel、小智或Pages；v2数字仅历史。还要配置副本安全升级工具、身份鉴权/小智交接、完整站点。
8. Analysis路由字段现在在新调用schema中列required，保留旧持久模型默认兼容；提示增加情绪强度/未知分类锚点。Critic明确verdict与issue code、非行动不要求卡片。debug3仍见无依据academic/self标签及矛盾no_topic_probe+open_question通过，需继续修复验证，不能标最终质量通过。
9. 三轮live与本轮测试进程均已结束；无付费后台进程需要接续等待。下一次应从新证据目录继续，不重跑已结束句柄。

## 闭环升级进展（2026-11-04 续）

- 新增 ExerciseProtocol；Planner/Critic读取过滤后的练习条件，Snapshot保留preferred_exercise。泛化“试办法”许可只产生具体练习邀请，用户再次明确同意才播放；Cry不再默认授予呼吸练习。每种练习有拒绝/退出/反馈参数测试。
- SupportReference（ID、版本、类型、步骤）写入TurnPolicyFrame、OutputEvent、InteractionEvent与MemoryItem；记忆归因必须匹配实际明确反馈事件，伪造版本被拒绝。无归因“好多了”不生成策略有效性记忆，服务器completed仍仅是执行事实。
- Talker默认正文流，兼容旧标签校验；首句不再等标签/整段完成，历史正文直接供模型，跨轮问题预算控制连续追问。`先停在这里`进入安静；等待策略模板不再追问；删去无依据泛化夸奖。
- debug4（2段×5轮）真实27条角色记录全部结构成功，另有1个本地矛盾候选拒绝、1次risk超时watch。S16实际执行，练习执行但把用户睡前暂停选为呼吸，故不能记为质量通过。已增加指定练习过滤，并将候选自身约束冲突接入一次修订+复核；待真实复测。4个动态输出首句约1704–2000ms，无标签遗漏；这不是30次最终性能结论。
- `closed-loop3.txt`有1项失败（136通过）：完整练习协议重复进入Planner/Critic使二次复核超32k预算。压缩到实际条件字段后原检查通过；没有提高预算。`closed-loop5.txt`：141 passed /3 deselected，Ruff/format通过。
- `prepare_audio --bind-config`在独立部署副本写入路径/时长和audio_manifest；实际24个固定文件均核查，`fixed-audio-live1.txt`。正文/声音/model/cache hash/文件hash/停顿/时长绑定，改词或错文件不能进入demo。当前acceptance仍null，最终真实回放未完成。
- `upgrade_config`包含已发布v2默认资源基线；配置先在临时副本校验再备份更新，settings按字段保留定制，已绑定音频可随协议更新保留。实际副本升级后重跑changed=[]。JSON新增字段兼容旧持久记录，目前未改变SQL结构。
- `access.patch`新增WS认证与连接日志脱敏；独立随机凭据映射到服务端user_key，伪造device-id不能访问另一用户；原六核心补丁保持。`provision_device`只向忽略目录写凭据，不打印token；probe/bench自行建立合成身份。已在vendor应用，两次检查幂等。服务正在启动，日志`xiaozhi-server1.log`；尚未运行新WS探针。
- 观察台新增检索候选/拒绝依据表，已有JSON可显示版本与反馈归因；浏览器实际验证尚待。

下一步：检查小智启动与鉴权、运行本机语音探针；最终固定质量集与逐策略live覆盖（区分强制/自然）、30次语音；收齐demo真实回执，隔离wheel/迁移/配置测试，站点与架构/文档、推送部署。旧版交付数字均不作为本轮通过证据。
