# 课程研究升级验证 · 2026-11-04

本报告对应研究驱动升级。v2原始验收保留在 [2026-11-03历史报告](VALIDATION_V2_20261103.md)，历史96项测试、40次语音及旧模型配置不作为本轮结果。实际范围为合成案例/成年成员课程演示；硬件测量交由小智同学完成。

## 代码审查修复复核（2026-11-04）

两个P2均有回归测试：`test_project_site.py`用真实临时Git仓库检查历史/当前提交、已修改及未跟踪内容不会串入导出、失效ref不覆盖原JSON；`test_exercise_eligibility.py`覆盖通用邀请、具体邀请和中止恢复，分别检查排除条件、合法重评与模型超时，使用屏障验证重评未完成时不能抢先播放，并区分普通语音确认与新增哭声信号。场景11保留完整中止恢复，增加重评等待步骤。

正式离线入口复核：**165 passed / 3 online deselected**，Ruff与格式检查通过，新增13项参数化检查。以下原课程验收表保留当时152项基线，不混写为新测量。

真实Aihubmix定点复测两段合成对话（仅限定呼吸练习目录，未强制模型候选）：原计划已选择呼吸练习后，补充身体关注不适，后续同意未执行旧练习；补充安全环境后，旧邀请失效，重评后重新邀请、再次同意才播放。34次后台角色调用均返回有效结果，9个任务completed、1个被合并、1个最终评审拒绝；两个结束整理均完成。第二段有2次风险API超时回退watch，保留失败，没有调整deadline或重试预算。结果证明这两条修复路径，未重新测量TTS、语音性能或硬件。

原始合成证据在主工作区忽略路径`artifacts/review-p2-fix/live/report.json`及同目录数据库；测试命令仍为`./scripts/run.ps1 test`。本次隔离修复工作目录复用已有解释器运行`scripts/check.py`，避免影响其他会话的分支和主页修改。

## 工程与集成

| 检查 | 本轮结果 | 本地证据（artifacts/autonomous-upgrade/） |
| --- | --- | --- |
| 正式离线入口 | Ruff、format通过；152 passed / 3 online deselected | release-check16.txt |
| 内容链路 | 六类策略、三练习逐项过滤/许可/拒绝/退出/反馈，来源与版本归因；危机独立接管 | test_course_strategies、test_course_exercises、test_content_catalog、原v2并发/安全检查 |
| 课程准入 | 10条目回执绑定当前内容/提示词摘要；实际音频验证后Config(mode=demo)通过 | demo-admission-final.txt；config/content_manifest.yaml |
| 固定音频 | 24段缓存文件；睡前29.9s、自然呼吸36.25s、外部注意33.7s，均含停顿 | fixed-audio-final.txt；脚本、声音、WAV hash及实际时长绑定 |
| CLI | fake/live均实际运行policy、memory、jobs与结束；live前台正常，后台Critic一次超时可见，结束done | cli-fake-final.txt、cli-live-final.txt及各自合成库 |
| 观察台 | 实际选择deliberation，显示触发、目录候选、失败修复、Critic candidate=1、accepted、支持版本/步骤及persistent反馈；界面异常0 | browser/dashboard-final-selection.txt、dashboard-final-details.txt、dashboard-final.png |
| wheel与迁移 | 隔离site-packages四角色fake/CLI、配置与迁移资源、v1备份/事务升级/重跑幂等、保留定制配置 | wheel-check4.txt；wheel-demo.txt（隔离包实际demo CLI） |
| 小智 | 本机认证、WebSocket/Opus解码、SenseVoice ASR、固定危机、abort后无旧帧、重连和结束均已执行 | xiaozhi-probe-final.json / log；最新版完整通过 |
| 网站与图 | 五张Archify自动四关通过；实际浏览器目视、主题、125%缩放；站点筛选/空态/展开/键盘/窄屏、九项内部资源200 | diagram-*-final2.json；browser/round-08至20；3条异常来自浏览器扩展，项目脚本异常0 |

原v2的V2-01～V2-24检查保留并随完整离线套件通过。当前增量契约使用可选JSON字段，SQL仍为正式v2迁移；没有假设改版本号就完成迁移。配置升级是有基线的三方合并，不覆盖用户定制。

## 真实模型与质量

最终使用 Aihubmix：Talker/Risk/Brief/Critic/Delta=qwen-flash，Analysis/Planner=qwen-plus，Memory/End=gpt-4.1-mini；TTS=gpt-4o-mini-tts/coral。关闭thinking与SDK自动重试。选择基于具体schema/时延探针：qwen-plus用于情境和规划，轻量模型用于独立短评，gpt用于较快的记忆整理；all-gpt调试未稳定选中目标，未采用。JSON schema接口不保证语义或来源正确，仍保留本地校验与一次共享修复预算。

预先固定17段：九段目标目录覆盖与八段自然选择。两次完整执行各记录73个输入样本（新会话/播放完成等控制步骤另算，N08最后idle_end驱动捕获曾失败），随后8+1+2+1段定点补测。具体逐段审读、失败与修复见 [QUALITY_REVIEW](autonomous-upgrade/QUALITY_REVIEW.md)；全部分母、角色状态、摘要、Token与时延见 [VALIDATION_SUMMARY.json](autonomous-upgrade/VALIDATION_SUMMARY.json)。

第二批9/9目标实际执行，包含单独练习许可；76个后台任务为61 completed、4 partial、8 rejected、2 timed_out、1 expired。205条角色记录中197 completed、6 schema_error、2 timed_out。41个动态文本成句样本P50 1281ms / P90 1406ms；75个开始执行的后台任务P50 10729.5ms / P90 15422.6ms。一次Talker回退保留，没有用固定模板冒充模型生成。

修复证据：N01明确拒绝不再邀请；T04“愿不愿意”转述不再撤回；T03孤立闭引号不发声，错误来源不入库、一次修复后结束done；N08结束会话移除后回放仍完整；N04已有边界阻止邀请时直接输出“按你前面说的，先不替你安排办法。”，避免再由Talker生成未许可建议。final6仍有一次后台超时，前台与结束正常，保留为可观察失败。

保留的语言限制包括概括性肯定、重复问感受、学校支持可用性表述偏确定、边界目标不明确时保守阻止行动。它们不被包装成全部对话质量通过。课程内容准入表示逐条已完成工程/真实链路审读；不表示每次随机生成均合格，也不证明临床效果。

Token统计把provider与estimated分开标记。第二完整批次记录输入442918、输出35880 token，其中311条provider用量记录、5条保守estimated；包含后台、Talker与Risk，排除TTS、调试和其他批次，不代表账单价格。所有原始失败保存在独立目录，公开文件只含合成汇总。

## 语音、优化与参考目标

第一批voice-final1：30/30普通动态成功、0回退/失败，单客户端顺序输入、后台正常开启，没有同时运行质量回放。文本首句P50 1257.5ms / P90 1641ms；客户端首包P50 3680ms / P90 4062ms；服务端发送完成P50 9414ms / P90 11000ms。随后增加最后的边界输出处理，最终版本另采30次，记录在voice-final2，不混合成单一版本统计。

最终版本voice-final2：**30/30动态成功，0回退、0失败、0超时**；21/21后台角色completed，8/8认知任务completed，结束done。与上一批分开报告。完整分段指标如下（均为输入到该里程碑，除标注差值外；毫秒）：

| 指标 | n | P50 | P90 |
| --- | ---: | ---: | ---: |
| 文本首token | 30 | 1187.5 | 1359 |
| 文本首句/闸门放行 | 30 | 1257.5 | 1421 |
| 音频排队/TTS开始 | 30 | 1273 | 1421 |
| TTS完成 | 30 | 3539 | 3937 |
| Opus首包ready/sent | 30 | 3586 | 3984 |
| 客户端首包 | 30 | 3609 | 4015 |
| 服务端发送完成 | 30 | 9273 | 11031 |
| TTS本身（complete−start） | 30 | 2266 | 2582.7 |
| 编码到ready差值 | 30 | 47 | 64.5 |
| 后台任务执行 | 8 | 12610.7 | 15316.3 |

单顺序客户端、31个生成句均未命中固定音频缓存，普通后台开启，未同时跑质量回放；没有缺测首包。前八行沿用bench工具的经验分位数；派生时长/后台用插值分位数，原始值与汇总脚本均保留。最后一批provider记录81条，输入73521、输出5681 token，TTS字符费用与账单金额未估计。

最新小智探针实际通过：固定初次wake首包93ms、普通动态3140ms、危机109ms、再次wake47ms；abort→stop为0ms（计时分辨率内），随后无旧binary；真实Opus音频输入由SenseVoice转写为合成样本“早上9点至下午5点”，回应首包3797ms，两个会话结束done。probe3等早期探针与错误测量保留，当前结果来自独立的probe-final。设备播放未测。

已经实施：Talker正文流直接分句（不用等待协议标签）、紧凑角色上下文、Analysis去掉不属本角色的记忆输出、剩余Token修复预算、独立风险与后台槽位、有界下一句预取、固定音频接管及generation取消。普通首包仍受外部文本生成和完整WAV合成主导；没有填充音频或降低指标定义。

参考目标仍为900ms文本首句、1.8s真机首响、常规后台8s。当前文本首句与后台未稳定达到；本机首包不能代替真机首响。真机播放ACK、扬声器首响、麦克风和物理按钮由硬件同学按 [XIAOZHI_HANDOFF](XIAOZHI_HANDOFF.md) 测量。

## 复现与范围

新版[GitHub Pages](https://hhuang999.github.io/companion-doll-backend/)已部署，[工作流41696251499](https://github.com/hhuang999/companion-doll-backend/actions/runs/41696251499)成功。浏览器逐张验证五个架构视图、首页真实汇总、策略筛选和390px窄屏；九项内部资源均HTTP 200。发布记录与本地证据索引见[实施状态](autonomous-upgrade/IMPLEMENTATION_STATUS.md#github-与-pages-发布验收)。

命令见 [V2_OPERATIONS](V2_OPERATIONS.md)、[CONTENT](CONTENT.md) 和 [展示脚本](autonomous-upgrade/DEMO.md)。检查原始产物必须使用新输出目录；公开仓库不含API key、数据库、客户端令牌或私人音频。新TASK已授权由Codex完成课程内容核查与验收，固定S03–S19及人工签字不再是本课程发布前置条件。
