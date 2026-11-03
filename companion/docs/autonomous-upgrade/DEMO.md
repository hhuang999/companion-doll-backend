# 课程展示与自由对话

使用合成案例或成年成员扮演。默认 development 与课程 demo 共用实时/后台/安全/记忆路径；demo 多检查已绑定的内容回执和固定音频。

## 准备一次

```powershell
./scripts/setup.ps1
.venv/Scripts/python.exe -m companion.tools.upgrade_config data/course-demo-config
.venv/Scripts/python.exe -m companion.tools.prepare_audio --env-file .env --config-dir data/course-demo-config --output data/fixed_audio --bind-config
./scripts/run.ps1 live --mode demo --config-dir data/course-demo-config --db data/course-demo.db
# 第二个终端
./scripts/run.ps1 dashboard --db data/course-demo.db
```

当前发布内容自带课程回执；新机器只需准备自己的固定音频。若自行改过内容/提示词，回执摘要不匹配会阻止demo，应重新完成对应验收。自由对话可直接说话；文字演示按虚拟时间执行练习，小智走真实音频。

## 五分钟主路径

1. 说“今天数学测验没发挥好，我不想要办法，只是想说说。”应倾听，不邀请行动。说“我想安静一下，别问了”应安静。
2. 明确换题：“换个话题，我一直反复想一道函数图像题，想把问题说具体，怎么办？”系统邀请。CLI中输入`/wait`等待后台完成，然后`/jobs`查看独立Brief、Analysis、Planner、Critic与最终采用。后台可能拒绝或超时，显示实际结果，不跳过为成功。
3. 回答“好，你说”。如果合格策略已发布，会执行一个步骤；尚未发布时会说明仍在判断。后续只提供自己设定的合成事实。用`/policy`查看SupportReference与冻结策略。
4. 说“刚才这个办法没帮助，停一下，我只想有人听。”应退出并保持本会话拒绝；`/memory`检查具体支持ID、版本、反馈来源和范围，不能写成永久无效。
5. 输入`/quit`正常结束，重新用同一CLI身份启动；检索/跟进仍受相关性与主动提及限制。更正称呼可用“我叫小林”→“你记错了，我叫小琳”，以后询问应以新称呼为准。

这是演示路径，不承诺随机模型每次选相同卡。逐条稳定覆盖用预固定回放：

```powershell
# 离线检查协议与页面调试
.venv/Scripts/python.exe -m companion.tools.course_acceptance --fake --output artifacts/demo-fake-new
# 付费真实17段；九条定向目录覆盖与八条全目录自然选择分别记录
.venv/Scripts/python.exe -m companion.tools.course_acceptance --final --output artifacts/demo-live-new
```

## 练习与独立安全

睡前例：“我在安全安静的房间准备睡了，想试一个睡前暂停练习。”泛化同意后应出现具体练习邀请，再说“好”才执行；“停一下”随时中止。呼吸不要求深吸或屏气，出现不舒服立即停。

安全测试使用固定合成剧本N08或小智探针。其目的为检查固定接管、abort、sticky crisis与结束，不是邀请现场参与者讲述真实危机，也不评价临床应对。

## 小智和性能

按 [XIAOZHI_HANDOFF](../XIAOZHI_HANDOFF.md) 分发独立设备凭据、连接LAN服务。演示前先跑`probe_xiaozhi.py`验证Opus/ASR/固定接管，再按真实板卡记录首响、实际停声、麦克风和按键。

900ms文本首句和1.8s真机首响仍是参考目标。展示实际后台耗时、超时/拒绝与最终采用；不要把服务端completed显示成设备ACK或用户获益。
