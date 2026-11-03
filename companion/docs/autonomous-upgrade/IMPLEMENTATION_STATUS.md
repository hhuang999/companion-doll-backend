# 研究驱动升级：持续实施状态

更新时间：2026-11-04（Asia/Singapore）。权威任务：[TASK.md](TASK.md)。状态：本次可独立完成的开发、验收、文档与线上发布已完成；硬件检查交接。
分支 `codex/research-support-upgrade`；起点 `3cb20bc8b47ef15924ca1a3c6557951a5680cd0c`。
实现提交：319d59e、272e825、15c1fe2、4de1836、bc189f0、480d4a8、38fb8cf；网站与文档8c14c78、源码固定27c2062。任务分支已正常快进集成main，Pages已部署并在线检查。
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
| U01 §3、9.1 | 基线、独立分支、持久状态 | 完成；基线96检查，当前152通过；分支codex/research-support-upgrade |
| U02 §4.1 | 研究来源与外推限制 | 完成；16来源；research/EVIDENCE_REVIEW.md |
| U03 §4.2–4.3 | 五压力/四路径与筛选设计 | 完成；STRATEGY_DESIGN.md；六策略/三练习/反例/历史映射 |
| U04 §5.1、7 | 内容协议与课程准入 | 完成；content/*；course-release-1十条目回执，demo-admission-final.txt |
| U05 §5.2、6 | 角色、检索与默认主路径 | 完成；Analysis/Planner/Brief/Critic/Talker；各角色真实执行，保留失败与拒绝 |
| U06 §6、7 | 许可、退出、短练习与危机 | 完成；真实T01–T09/N08；blocked invitation固定确认；152离线含取消/安全 |
| U07 §5.2、6 | 反馈、范围记忆与恢复 | 完成；SupportReference全链；N07更正/重连与来源回归；结束恢复与清除测试 |
| U08 §6 | 迁移、配置与wheel | 完成；wheel-check4/wheel-demo、v1备份/重跑无重复、配置三方合并 |
| U09 §7、9.4 | 固定音频与时长 | 完成；24文件；29.9/36.25/33.7s含停顿；fixed-audio-final.txt |
| U10 §8 | 小智认证与交接 | 完成；access.patch保留六hook；XIAOZHI_HANDOFF.md；本机鉴权/协议实测 |
| U11 §9.2 | 策略与并发故障检查 | 完成；152 passed/3 online deselected；release-check16.txt |
| U12 §9.3 | 固定多轮质量审读 | 完成；17段两次完整及12段补测；QUALITY_REVIEW/VALIDATION_SUMMARY；措辞和超时限制保留 |
| U13 §9.4 | CLI、观察台、WS/Opus/ASR | 完成；CLI fake/live、观察台真实任务/反馈；xiaozhi-probe-final通过 |
| U14 §9.5 | 30次最终语音与性能 | 完成；voice-final2 30/30动态、21/21角色；首句1257.5/1421ms、首包3609/4015ms；参考目标未全达 |
| U15 §10 | 项目站与五张架构图 | 完成；自动四关与实际线上五图渲染通过，固定实现源码38fb8cf；桌面/390px/筛选/链接检查 |
| U16 §11 | 文档、提交与GitHub/Pages | 完成；正常push任务分支/main，Pages部署41696251499成功；浏览器证据见末节 |

## 实施决定

1. 保持当前模块化单体与有界 Agent 协议；研究资料离线核查并压缩成可执行内容，在线不逐轮联网搜索。
2. 课程内容准入将明确区分来源核查、自动审查、工程回放与适用范围；不能将机器核查记为人工/临床审核。
3. 新策略使用语义化 ID，保留已知 S16 映射与旧记录可读性；不猜测缺失 S03–S19 的原义。

## 实施过程记录（按时间保留，当前状态见顶部与末节）

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

## 质量、接口和安装复测（2026-11-04 01:43 续）

- 新固定17段场景 `config/course_scenarios.yaml`，T01–T09逐策略/练习限定目录；N01–N08自然选择。`tools/course_acceptance.py`记录全部输出、角色、发布、记忆与结束任务，区分debug/final，不伪造设备ACK。最终全量尚待。
- debug5（T01/T09）：S16执行，发现“分别”被误识别为“别”的边界；已修词法并增加回归。T09未执行，Analysis遗漏bedtime，Planner编造练习ID。debug6切Analysis/Critic到qwen-plus，长分析挤占20s预算导致多次超时及错误边界，保留失败。
- debug7/8压缩分析，恢复flash后仍出现错误quiet/no_private_space、额外source_refs；将线上Analysis的schema投影去掉记忆候选和不可达定义（持久契约兼容保留），专用memory/end继续整理记忆。debug8分析1719ms，但首轮误判quiet，具体邀请延迟至第3轮，练习未实际执行。没有扩大deadline。
- 当前配置：Analysis qwen-plus、Planner qwen-plus、Critic/Brief qwen-flash；缩短分析输出并保留原始证据约束。debug9已实际经历具体邀请→明确同意→bedtime exercise_plan，结束待完成；结果仍属于调试。
- 来源枚举动态限定到实际用户轮次/记忆/事件ID，支持反馈元数据完整投影给后台；来源和最终CAS仍逐项校验。
- `replay-source6.txt`、`routing7.txt`：142 passed /3 deselected，Ruff/format通过。当前对话的模型/提示更新发生在routing7启动附近，最终应再跑正式检查。
- 实际小智server1已运行。缺token/伪造device-id连接均1008拒绝。probe1曾错误将上一轮剩余句子计作危机缓存；probe2发现wake是control行；均保留失败。probe3修正后实际验证固定危机原文、abort后无旧帧、同身份重连、Opus/ASR、结束done。证据 `xiaozhi-probe3.json`/log。普通首包3406ms、ASR回合3844ms，缓存首包47–94ms；不是30次性能或硬件首响。
- `wheel-check2.txt`：隔离site-packages运行通过四角色fake、资源、CLI、v1迁移备份、重跑无重复、配置定制/幂等。初次pip缺失；uv沙箱PE入口安装受限，正常授权环境安装成功，失败日志保留。之后代码/配置还会更新，发布前重建最终wheel。
- 观察台实际启动8502，Ego TaskSpace 7/p1；已显示真实调试会话、后台角色和记忆。完整筛选/细节验证继续。浏览器脚本及快照 `artifacts/autonomous-upgrade/browser/`；用户可见提示已去掉过时占位内容说法。
- 新接口文档 `companion/docs/XIAOZHI_HANDOFF.md` 覆盖凭据、LAN、hello/text/Opus/abort、重复/乱序限制、恢复、测试和硬件分工；旧README与发布站点仍待同步。

当前运行：小智server1（工具session20468，旧配置加载，最终性能前重启）；观察台8502（session73189）；debug9（session78786）。所有更早调试与wheel检查均已结束。下一步检查debug9并运行最终固定集；不要把debug通过写成最终质量通过。

## 最终回放与网站推进（2026-11-04 续）

- `4de1836` 已提交：角色路由/投影、剩余预算修复、固定17段验收工具、来源限制、schema探针结论及小智探针修正。
- 当前模型 Analysis/Planner=qwen-plus；Brief/Critic/Delta=qwen-flash；Memory/End=gpt-4.1-mini。all-gpt debug10未选对目标；混合debug11 T04/T09执行。原失败保留。
- quality-final1 完整17段：8/9定向执行，T04失败；N08记录驱动错误。quality-final2：9/9定向执行，但N01拒绝仍邀请、T04转述误撤回、T03闭引号独立输出。已修复主路径，quality-final3正在补测8段受影响场景。N08驱动移除session已修复且fake回归通过。
- Memory/End错误来源纳入一次有界修复，最终仍校验数据库来源和用户隔离。当前 `review-fixes12.txt` **150 passed /3 deselected**，Ruff与format通过。
- 本地新站点完成研究映射/策略过滤/练习/反馈/证据/运行入口；浏览器 TaskSpace7 p2。桌面实际1600/1422/853及390宽无横向溢出，reduced-motion开启后scrollBehavior=auto。页面和图仍待最终数据、链接与发布。
- 四张新图已finalize通过，固定引用4de1836；overview布局调整导致阅读缩放失败，恢复原布局，保留一个已标记跨线，未声称零交叉。第五张content待最终代码commit后重新固定源码行数并finalize。
- 尚待：完成真实补测/逐段审读、最终30动态语音、最新wheel、课程demo真实回执、观察台细节/图视觉检查、完整报告与GitHub/Pages发布。
- 当前运行：小智旧配置session20468；观察台8502/session73189；站点8765/session66209；quality-final3/session51610。quality-final1/2已结束。性能前重启小智到最终配置。


## 最终收口（2026-11-04，继续执行入口）

- 480d4a8：输出护栏复测修复；其后新增boundary_hold，阻止邀请后直接确认边界。final6 N04实际命中且end done，仍有1后台超时。当前release-check16：152 passed/3 deselected，Ruff/format通过。
- 已完成17段固定集逐段审读，保留final1/final2完整批次及final3–6补测；QUALITY_REVIEW与VALIDATION_SUMMARY是公开汇总。final2九目标执行；假模型与目录限定不算自然选择。
- 10条目课程回执已绑定package_digest，24固定音频核验后data/xiaozhi-config的demo准入实际通过。wheel-check4从最终wheel/site-packages运行，fake四角色/CLI、迁移/备份/幂等、配置定制保留通过。
- CLI fake/live通过；live有一次Critic超时，结束done。观察台8503加载final3/T04：实际候选safe_support、独立评审candidate=1、accepted、明确反馈course-1.0/step3/persistent可见，无界面异常。
- 五图已自动四关+目视；站点筛选/空态/长内容/键盘跳到正文/窄屏/主题/缩放检查；9内部资源200，3浏览器扩展错误与项目分开，项目异常0。尚待最终内容和线上检查。
- voice-final1完成30/30动态成功，首句P50 1257.5ms、客户端首包3680ms。新边界修复后voice-final2正在执行最终30次（session80090，server final3/session21191）。性能批次期间无质量回放并发。需要等结束再跑最新小智协议探针、记录准确性能、部署GitHub/Pages。
- 新状态：开发/内容/安装可交付，性能最终批次、最新协议复测和发布收口未完。不要以本段为最终交付。


## 发布前验证收口

- voice-final2已结束：30/30动态成功、0回退/失败/超时，首句1257.5/1421ms、首包3609/4015ms；31句均未命中固定音频缓存。8/8后台任务、21/21角色completed，provider输入73521/输出5681 token。此前voice-final1独立30/30保留，不混版本。
- xiaozhi-probe-final实际通过wake/普通/危机abort/重连/Opus真实ASR，两个结束done；首包93/3140/109/47/3797ms。无ESP32播放ACK或真机测量。
- 最终wheel-check4及隔离wheel-demo通过；CLI实时一次Critic超时保留、结束done；当前文档已明确历史与课程结果、范围和未达项。
- 目前只剩发布提交、普通push/main集成、Pages在线内容/链接检查。服务可留供用户使用：小智8000/session21191、观察台8503/session14877；本地站8765/session66209。所有付费验收任务已结束。

## GitHub 与 Pages 发布验收

- 2026-11-04，任务分支 `codex/research-support-upgrade` 推送成功，`main` 从3cb20bc正常快进到27c2062；后续仅补充本发布记录与站点文档引用固定值。
- [Pages部署41696251499](https://github.com/hhuang999/companion-doll-backend/actions/runs/41696251499) completed/success；来源main:/docs。
- 已实际访问 [项目网站](https://hhuang999.github.io/companion-doll-backend/)：六策略、三练习、16来源、152检查、17段场景、30/30语音及真实延迟均显示；五张架构图逐张加载与目视检查，九个内部资源HTTP 200。
- 线上“只想被听见”进入无行动空态，重置恢复六策略；390px视口无横向溢出。GitHub插件读回新版README与固定提交的小智交接文档成功。
- 本地证据：`artifacts/autonomous-upgrade/browser/pages-online.json`、`diagrams-online.json`、`pages-online-mobile.json`及对应截图；全升级115个变更文件通过实际凭据值扫描，原始API/设备凭据与运行数据保留在忽略路径。
- 已完成全部可独立完成范围。仍保留语言精修、偶发角色超时、900ms/8s参考性能差距；真机首响、停声、麦克风和物理交互按XIAOZHI_HANDOFF由硬件同学验收。此状态不代表真实未成年人或临床适用性验证。
