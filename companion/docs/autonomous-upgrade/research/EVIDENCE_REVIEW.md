# 研究证据审阅与策略转译（课程原型）

核查日期：2026-11-04（Asia/Singapore）。范围：中国大陆高中生日常压力作为设计情境；实际课程演示只使用合成案例或成年团队成员。此文件核查研究和设计依据，不是心理治疗方案，也不是内容包的运行验收报告。来源编号供策略配置、覆盖矩阵和公开站点固定引用。

## 核查结论与需要纠正的表述

1. **五类压力是产品分类，不是量表原有五因子。** ASQ-CN 在 420 名中国中学生中提取的是六个因子，包括关系、学业未来、学校与闲暇冲突、父母权威等；其样本并非仅高中生。[E01] 学业、社会评价、关系、未来迷茫、自我压力适合做可重叠的交互标签，但不应称为已验证的诊断分类或五因子量表。
2. **“四条路径”是可询问的线索，不是已确证的通用致病机制。** 浙江三波队列发现学业压力与后续症状的关联可由睡眠和孤独的统计中介描述，但这是自陈、地区性队列，统计中介不能证明因果链，也没有测试玩偶干预。[E02] 反复想的具体/抽象加工实验提供机制线索；完美主义担忧与症状的元分析提供相关证据；它们也不证明语音短步骤能降低症状。[E06][E07]
3. **社会评价与求助障碍应影响表达方式。** 社会评价威胁的实验元分析主要测量急性皮质醇反应，不能直接推导高中生抑郁风险或“不评价的玩偶会提高求助率”。[E03] 长沙 3480 人横断面调查：过去一年 73.0% 表示求助；在求助者中 99.3% 使用非正式渠道、13.9% 使用正式渠道，其中 10.2% 找心理老师（渠道可重叠）。[E04] 研究链中的“10.2% 找心理老师”可保留，不能写成所有求助者中正式求助仅 10.2%。跨国综述认为污名/尴尬、保密和信任、自力更生是常见障碍，但大部分研究来自澳大利亚和美国。[E05]
4. **已有干预的时长和支持者条件不能被短语音继承。** WHO/UNICEF EASE 面向 10–15 岁、由受训且受监督的非专业人员开展七次约 90 分钟小组活动，并另有照护者课程。[E08] Bluth 等的自我关怀研究为美国 59 人、八周主课程加后续课程；中国高中生生涯干预为教师主持五周课程。[E09][E11] 本项目仅借用机制和低负担的表达/选择步骤；改编本身的效果尚未验证。
5. **WHO 心理急救适用危机。** 手册目标是近期经历严重危机的人，明确不强迫帮助。[E13] “看、听、连接”可作为风险通路的人本原则，也可借“尊重意愿、寻找安全支持”作为一般沟通原则；不把完整 PFA 声称为日常每轮干预。
6. **ESConv 与 PPDPP 是工程参考。** ESConv 是有策略标注的支持对话数据和框架，不是临床疗效试验；阶段可灵活使用，不应规定每段对话必须走到行动。[E14] PPDPP 有“策略动作映射为预定义自然语言指令”的机制，但论文的增益来自 SFT、模拟对话与强化学习训练；现有 v2 只借策略投影形式，不继承其效果数字，也不引入训练或“模型判断用户问题已解决”的奖励目标。[E15]

## 已读取来源与适用范围

`全文`表示实际打开正文或官方手册并阅读相关方法、结果、限制；`摘要`只支持相应摘要中的论断。以下均为来源自身的论文页、开放作者稿或官方手册，未用二手转述填补未读细节。

| ID | 来源、类型、对象与实际读取范围 | 支持本项目的具体判断与局限 |
| --- | --- | --- |
| E01 | Ye、Cui、Yang、Liu，2019（在线 2018），[Evaluation of the Factor Structure of the Adolescent Stress Questionnaire in Chinese Adolescents](https://pmc.ncbi.nlm.nih.gov/articles/PMC6669116/)，DOI 10.1177/0033294118792686；中国中学生 N=420，量表因子研究；**全文**：摘要、方法、六因子及讨论 | 压力领域多样，ASQ-CN 六因子 42 条、内部一致性 .82–.90；不能证明本项目五类就是量表因子，也不评价任何支持策略。 |
| E02 | Wang、Wang、Yang 等，2025，[Academic Burden and Emotional Problems Among Adolescents: A Longitudinal Mediation Analysis](https://onlinelibrary.wiley.com/doi/10.1002/jad.12471)，DOI 10.1002/jad.12471；浙江初高中生 N=2965，三波观察队列；**全文**：方法、结果、讨论、限制 | 学业压力和后续抑郁/焦虑症状相关，睡眠和孤独的统计中介分别占抑郁关联的 31.0%、26.8%；地区、疫情时期、自陈和残余混杂限制因果推断。未测试睡前脚本或社交练习。 |
| E03 | Dickerson、Kemeny，2004，[Acute stressors and cortisol responses](https://pubmed.ncbi.nlm.nih.gov/15122924/)，DOI 10.1037/0033-2909.130.3.355；208 个急性压力实验的元分析；**摘要** | 不可控且可能被负面评价的任务通常诱发更强急性皮质醇反应。实验任务/生理反应不能直接推出中国高中生的长期心理风险或产品效果。 |
| E04 | Zhao、Hu，2022，[A multilevel model of the help-seeking behaviors among adolescents with mental health problems](https://pmc.ncbi.nlm.nih.gov/articles/PMC9478167/)，DOI 10.3389/fnint.2022.946842；长沙四所初高中 N=3480，横断面自陈；**全文**：摘要、求助定义、表格/讨论（PMC 检索全文和期刊 PDF） | 帮助来源同时包含朋友、家人、教师和正式服务；73.0% 求助，求助者中非正式 99.3%、正式 13.9%，心理老师 10.2%。单地抽样、自陈、渠道重叠；不能推断本产品会改变求助行为。 |
| E05 | Gulliver、Griffiths、Christensen，2010，[Perceived barriers and facilitators to mental health help-seeking in young people: a systematic review](https://pmc.ncbi.nlm.nih.gov/articles/PMC3022639/)，DOI 10.1186/1471-244X-10-113；22 项青少年/青年研究的系统综述；**全文**：摘要、纳入、结果、讨论（检索全文；直接打开 PMC 时遇验证码） | 污名/尴尬、保密和信任、识别困难、自力更生常见；22 项中澳大利亚 10、美国 9、中国 1，求助促进因素证据较少。只支持降低评判感和给用户控制权的设计动机。 |
| E06 | Leigh、Taylor、Cole、Smith，2025，[Why is rumination unhelpful in adolescents? Two studies examining the causal role of abstract processing](https://ora.ox.ac.uk/objects/uuid%3A1bfdd831-ddfe-4efb-9dab-7b802d9ff8af/files/rrj430622m)，DOI 10.1016/j.jad.2025.03.058；英国 11–14 岁青少年，两项抽象/具体加工实验；**全文**：任务、比较、结果、讨论 | 具体加工相比抽象反复想在实验任务中伴随更好的社会问题解决和更少负面未来想法。测的是近端任务表现，不是抑郁治疗或一轮聊天的效果；年龄、文化需外推。 |
| E07 | Lunn、Greene、Callaghan、Egan，2023，[Associations between perfectionism and symptoms of anxiety, obsessive-compulsive disorder and depression in young people](https://pubmed.ncbi.nlm.nih.gov/37194469/)，DOI 10.1080/16506073.2023.2211736；6–24 岁，121 项研究元分析；**摘要**（全文链接未能稳定获取） | 完美主义“担忧”与抑郁症状汇总相关约 r=.40；高标准追求和担忧不能混为一谈。相关关系不能证明改写自我评价会产生疗效。 |
| E08 | WHO/UNICEF，2023，[Early Adolescent Skills for Emotions (EASE): group psychological help](https://iris.who.int/bitstream/handle/10665/374996/9789240082755-eng.pdf)；10–15 岁逆境社区青少年，官方干预手册；**全文**：范围、结构、监督、Calming My Body / Changing My Actions / Managing My Problems、停止和转介 | Stop–Think–Go 要求选择“小、可解、具体”的问题；识别感受、轻量行动、缓和身体均是结构化技能。EASE 需培训、持续监督、七次小组及照护者参与；只适合机制借鉴。 |
| E09 | Bluth、Lathren、Park 等，2024，[Feasibility, Acceptability, and Depression Outcomes of a Randomized Controlled Trial of Mindful Self-Compassion for Teens](https://self-compassion.org/wp-content/uploads/2024/06/Bluth2024.pdf)，DOI 10.1002/jad.12277；美国亚临床抑郁青少年 N=59，八周小组+延续课程、主动对照随机试验；**全文**：方法、结果、限制 | 参与者的症状轨迹优于健康生活课程对照；样本小且以白人女性为主，两组自我关怀都增加。仅支持温和自我对话有进一步研究价值，不能据此承诺一句话减少抑郁。 |
| E10 | Filia、Eastwood、Herniman、Badcock，2021，[Facilitating improvements in young people’s social relationships to prevent or treat depression: A review of empirically supported interventions](https://www.nature.com/articles/s41398-021-01406-7.pdf)，DOI 10.1038/s41398-021-01406-7；青少年/青年人际干预叙述性综述；**全文**：检索范围、IPT-A 结构、沟通分析/角色练习与证据限制 | 沟通分析和角色练习存在于人工 IPT-A 中；可借“先理解冲突、再练习一句可选择的表达”。临床疗程和治疗关系不可缩成自动咨询；欺凌、虐待、明显不安全关系应转安全通路。 |
| E11 | Chen、Chen、Ling、Gu，2022，[An Online Career Intervention for Promoting Chinese High School Students’ Career Readiness](https://pmc.ncbi.nlm.nih.gov/articles/PMC8784529/)，DOI 10.3389/fpsyg.2021.815076；江苏高一 N=957，五周教师主持在线课程/对照；**全文**：干预、结果、限制 | 探索兴趣和获取可靠专业信息与更高生涯探索、较少信息困扰相关。干预包括教师、测评和数据库；聊天中只能帮助选择下一步可核查的信息源，不能提供未经核实的选科/录取建议。 |
| E12 | Scullin、Krueger、Ballard、Pruett、Bliwise，2018，[The effects of bedtime writing on difficulty falling asleep](https://pubmed.ncbi.nlm.nih.gov/29058942/)，DOI 10.1037/xge0000374；美国健康青年成人 N=57，五分钟书面待办/已完成任务随机比较及睡眠多导；**摘要** | 具体记录近期待办相比回顾已做事务，实验室入睡潜伏期更短。成年人、书写五分钟、单夜；玩偶的简短“留待明天”句不能宣称同样改善睡眠。 |
| E13 | WHO 等，2011，[Psychological first aid: Guide for field workers](https://iris.who.int/bitstream/handle/10665/44615/9789241548205_eng.pdf?sequence=1)；严重危机后现场支持手册；**全文**：适用范围、Look–Listen–Link、儿童章节 | 明确尊重意愿、不强迫、倾听并连接可信支持；主要范围是近期严重危机，不是普通考试压力的日常心理干预证据。 |
| E14 | Liu、Zheng、Demasi 等，2021，[Towards Emotional Support Dialog Systems](https://aclanthology.org/2021.acl-long.269/)，DOI 10.18653/v1/2021.acl-long.269；支持对话语料/框架；**论文页摘要与公开 PDF 中策略/标注段落** | 探索、安慰、行动作为可追踪的对话技能框架有用；数据来自训练过的人类支持者及质量控制，没有验证语音玩偶或临床效果。 |
| E15 | Deng、Zhang、Lam、Ng、Chua，2024，[Plug-and-Play Policy Planner for Large Language Model Powered Dialogue Agents](https://openreview.net/pdf?id=MCNqgUFTHI)（ICLR 2024）；对话策略规划实验；**全文**：方法、动作到指令映射、自博弈/训练与评价 | 可复用“选中策略 → 预定义短指令 → Talker”的接口思想；其结论依赖训练过的 planner 和模拟评价，不能当作当前无训练后台协作的质量证明。 |
| E16 | Dunning 等，2022，[Do mindfulness-based programmes improve the cognitive skills, behaviour and mental health of children and adolescents?](https://pmc.ncbi.nlm.nih.gov/articles/PMC9340039/)；青少年/儿童随机试验更新元分析；**全文**：主动/被动对照、随访、偏倚与限制 | 与主动对照相比，焦虑/压力改善很小，随访未见稳定差异，伤害报告不足。练习需有自愿入口、可停、短时长；对不适者改为眼睛睁开的外部感官定位或安静陪伴。 |

## 供内容包直接采用的策略转译

下面是本项目的原创短步骤提案，**均未作为短语音形式接受效果试验**。资格、许可、真实行为和反馈需由运行与回放检查验证。可共用一套“倾听 → 是否要一个小办法 → 一次只做一步 → 尊重拒绝”的外壳；同义表述不重复建卡。

建议内容 ID 与稳定来源映射：`concrete_replay`（既有 S16）→ E06；`small_problem_step` → E08/E06；`kind_self_talk`、`perspective_check` → E07/E09（后者是表达方法，不是另有疗效证据的独立机制）；`safe_communication` → E10/E13；`safe_support`、`social_small_step` → E04/E05/E10/E13；`values_exploration` → E11；`worry_parking` → E12/E02；呼吸/外部感官定位练习 → E08/E16。对只有原则级或观察性证据的条目，配置应记录 `adaptation=course_micro_step`，不得标作原研究已验证该步骤。

| 内容族 / 建议承接 | 目标与最小适用条件 | 排除、退出与反馈解释 | 来源 |
| --- | --- | --- | --- |
| 具体问题拆解；Planner 选卡、Talker 提供一个可选步骤 | 用户明确要办法；能指出目前可控制的一件小事。问“今天最想先处理哪一步”，只协助选择下一步，不给满清单。 | 未获行动许可、当下只想倾诉、问题不可由个人控制或涉及安全/欺凌时不推。说“没用”即停并记录明确反馈，不推出“该用户永远不适合解决问题”。 | E08、E06 |
| 反复想转具体经过；与拆解共用 `concrete_focus` 机制，避免两张同义卡 | 用户自己表达反复想且愿意短暂转向一个具体片段；问“最近一次是何时、具体卡在哪”，允许只说一处。 | 不要求详细回忆创伤/危险情境；反复讲述让人更难受时暂停。一次转向后的安静不等于改善。 | E06、E08 |
| 温和自我对话；可与“双重标准”合并 | 自我批评或以成绩定义价值且愿意试换一句说法；例“你会把同样的话对朋友说吗”，如果不适合则只承接感受。 | 不强迫自我肯定或“你很棒”；不把高目标本身当病。用户否定改写则停止。 | E07、E09 |
| 安全的人际表达与现实支持连接；一条卡内两个可选分支 | 关系紧张且对象相对安全、用户想说清一件事；协助拟一句“我感到…，我希望…”或选一个可信的人/学校渠道。 | 不能默认父母或老师安全；欺凌/虐待/控制或担心泄露时不做沟通劝和。用户未发出消息只记“草拟”，不记成功联系。 | E04、E05、E10、E13 |
| 未来探索；生涯信息只指向可靠的人/官方渠道 | 用户困于选科或未来且愿意探索；只问一个兴趣/可试的小方向，必要时建议向可信老师或官方招生资料核实。 | 不代替升学政策或专业决定；用户只想卸下焦虑时保持陪伴。发现信息过时或互相矛盾时不输出事实性决定。 | E11、E01 |
| 睡前担忧外置；可与原 bedtime 脚本结合 | 用户明确想结束并睡觉；可选“留一句明天再处理的事”，然后短收尾，不延长谈话。 | 不要求睡前列任务清单或承诺一定入睡；持续严重失眠需现实求助。拒绝后直接简短收尾。 | E12、E02 |
| 轻量身体/外部环境定位；练习脚本 | 用户愿意做不超过 90 秒练习；自然呼吸、不屏气或强制节奏，允许眼睛睁开、随时停；也可选外部感官定位。 | 呼吸让人不适、惊恐/躯体症状、当前环境不安全时停并换为普通陪伴或现实帮助。完成播放不等于有帮助；仅按用户明确反馈归因。 | E08、E16 |

共同边界：正常对话优先听懂事实和意愿；拒绝、安静、换话题、结束均可作为合格结果。行动、练习和现实联系均需当下许可，且一次只选一个焦点。系统应记录 `source_ids`、内容版本、适用/排除结论、运行状态和用户明确反馈；播放完、模型说“有效”、用户后来情绪变化是不同证据。

## 暂缓或排除

| 候选 | 处理与理由 | 可用替代 |
| --- | --- | --- |
| 自动实施 CBT-I、IPT-A、诊断、针对完美主义的治疗 | 原研究涉及评估、完整疗程或专业训练；本玩偶没有这些条件。 | 使用一般支持、短选择步骤，必要时连接可信专业支持。[E08][E10][E16] |
| 用反复保证、积极宣言、睡前“你一定能睡着”代替倾听 | 无法证实结果，也可能使拒绝或失败被忽略。 | 试探性承接事实，提供可拒绝的一步。[E05][E13] |
| 对家庭冲突统一推荐与家长和解；对孤独统一要求主动联系某人 | 安全和意愿未判明；混合情境中可能有欺凌、虐待、泄密担忧。 | 先识别安全的人或渠道；必要时进入安全流程。[E04][E05][E13] |
| 固定每四轮推进到行动、每次结束写行动承诺 | ESConv 阶段是支持者技巧，不是用户必须完成的治疗流程。 | 倾听、安静、拒绝或结束也可独立完成。[E14] |
| 依赖向量库或每轮联网研究检索 | 当前目录规模有限、规则与适用条件关键，语义相近不足以证明可用。 | 版本化结构化目录 + 确定性过滤 + 后台 Agent 评审；在线不访问论文。 |

## 可公开叙述与后续验证重点

公开站点可说：研究启发了压力标签、低评判表达、聚焦小问题、可选练习及安全现实支持；课程原型通过工程测试验证选择、许可、取消和反馈链路。不得写“玩偶降低抑郁”“防止自伤”“提高求助率”“EASE/自我关怀试验证明我们的短语音有效”。每张启用卡仍需独立通过来源一致性、排除条件、运行行为、真实模型多轮质量和内容准入检查。研究文献不能替代这些运行结果。
