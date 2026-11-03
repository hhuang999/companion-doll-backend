# 课程内容准备与准入

适用范围：合成案例或成年团队成员扮演学生，面向中国大陆高中生日常压力的课程研究原型。`course-1.0` 包含六类支持、三段短练习及固定危机支持文本。旧“固定17张卡＋人工签字”规则已由 [TASK](autonomous-upgrade/TASK.md) 的新授权替代。

## 内容与证据

`cards/*.yaml` 的 protocol 保存机制、适配限制、版本、证据ID、最少信息、适用/排除、许可、步骤、退出及反馈解释。启用ID为 S16、kind_self_talk、safe_communication、safe_support、values_exploration、worry_parking；历史映射与选择理由见 [策略设计](autonomous-upgrade/STRATEGY_DESIGN.md)。

`exercises/*.yaml` 保存文本、停顿和 ExerciseProtocol。自然呼吸不屏气，外部注意可睁眼，睡前暂停要求明确睡前情境。哭声触发安慰/重评；策略邀请、具体练习邀请与执行许可分别判断。

`content_manifest.yaml` 分开保存16项来源和实际读取范围、逐项 Codex 自动核查、工程验收回执。enabled 表示可被来源校验后的 development 使用，不等于 demo 已通过。自动核查不冒充人工或临床审核。修改条目须重新核查并更新对应sha256；修改提示词也会使整包验收摘要过期。

## 准备部署副本

在仓库根目录执行，现有 dotenv 加载 `.env` 中的 AIHUBMIXKEY：

```powershell
.venv/Scripts/python.exe -m companion.tools.upgrade_config data/course-config
.venv/Scripts/python.exe -m companion.tools.prepare_audio --env-file .env --config-dir data/course-config --output data/fixed_audio --bind-config
./scripts/run.ps1 live --config-dir data/course-config --db data/course.db
```

升级工具先校验完整副本，再备份更改；settings按旧默认/现有值/新默认三方合并。自定义提示词和内容保留，冲突需维护者检查。重跑不重复修改。音频按文字、声音、模型生成缓存；工具把实际WAV路径、时长和audio_manifest绑定到部署副本。正文/文件hash与时长逐项核验，含停顿总长≤90秒；大音频不放wheel或Git。

## demo 放行条件

`--mode demo` 要求全部启用条目有完整协议，来源引用一致、自动核查hash匹配、固定音频存在且脚本/声音/时长一致，以及当前整包摘要对应的真实验收回执。回执逐项覆盖适用、排除、许可/拒绝、退出和反馈，分开列确定性检查与真实回放。缺失、失败、重复或过期回执均拒绝启动。

当前course-release-1回执已绑定10个条目，实际部署副本在24段固定音频核验后通过demo准入。公开wheel包含回执，音频在使用机器上准备。逐条证据见 [质量审读](autonomous-upgrade/QUALITY_REVIEW.md)。

当前状态以 [持续实施状态](autonomous-upgrade/IMPLEMENTATION_STATUS.md) 和 [验证报告](VALIDATION.md) 为准。准备音频不自动生成通过回执；FakeLLM不替代真实模型结果。来源研究只支持机制借鉴，不替代系统行为检查。

## 修改后的验证

```powershell
./scripts/run.ps1 test
# 17段预固定真实回放；目标目录与自然选择分别标记，会调用付费模型
.venv/Scripts/python.exe -m companion.tools.course_acceptance --config-dir data/course-config --final --output artifacts/course-replay-new
```

逐段审读回应、选择、许可、拒绝、取消与反馈，记录全部失败和超时。真实通过后更新manifest回执；使用新输出目录保留失败证据。内容、提示词或模型改变后按影响范围重新验证。

线上不读取研究全文、不用相似度绕过资格。中文关键词只给合格目录排序；无匹配可倾听。播放完成是执行事实，表示有帮助是明确反馈，两者都不是改善问题的因果证据。
