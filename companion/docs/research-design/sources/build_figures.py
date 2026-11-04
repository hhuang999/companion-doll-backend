"""Rebuild the editable diagrams; conceptual PNGs are generated separately."""

import json
import os
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
COLORS = {
    "teal": "#24746c",
    "blue": "#465aa0",
    "purple": "#805b96",
    "amber": "#a37428",
    "red": "#a24a4b",
    "gray": "#59666b",
}
FILLS = {
    "teal": "#e8f3ef",
    "blue": "#edf0fa",
    "purple": "#f2ecf6",
    "amber": "#fbf2df",
    "red": "#f9ebea",
    "gray": "#f0f2f2",
}


class Diagram:
    def __init__(self, name, title, subtitle, height=760):
        self.name, self.height = name, height
        self.items = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#718087"/></marker></defs>',
            '<style>text{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;fill:#243538} .edge{fill:none;stroke:#718087;stroke-width:2;marker-end:url(#arrow)}</style>',
            f'<rect width="1440" height="{height}" fill="#fbfaf6"/>',
        ]
        self.text(48, 52, title, 30, True)
        self.text(48, 88, subtitle, 19)

    def text(self, x, y, value, size=20, bold=False):
        self.items.append(
            f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{700 if bold else 400}">{escape(value)}</text>'
        )

    def box(self, x, y, w, h, title, lines=(), color="teal"):
        self.items.append(
            f'<g class="node"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{FILLS[color]}" stroke="{COLORS[color]}" stroke-width="1.5"/>'
        )
        self.text(x + 18, y + 33, title, 23, True)
        wrapped = []
        for line in lines:
            current, width = "", 0
            for char in line:
                advance = 19 * (0.57 if ord(char) < 256 else 1)
                if width + advance > w - 36:
                    wrapped.append(current)
                    current, width = "", 0
                current += char
                width += advance
            wrapped.append(current)
        if wrapped and 65 + (len(wrapped) - 1) * 28 > h - 10:
            raise ValueError(f"{self.name}: text exceeds box {title}: {wrapped}")
        for i, line in enumerate(wrapped):
            if line:
                self.text(x + 18, y + 65 + i * 28, line, 19)
        self.items.append("</g>")

    def arrow(self, points, dashed=False):
        coords = " ".join(f"{x},{y}" for x, y in points)
        dash = ' stroke-dasharray="7 5"' if dashed else ""
        self.items.append(f'<polyline class="edge" points="{coords}"{dash}/>')

    def save(self, foot):
        self.text(48, self.height - 27, foot, 17)
        self.items.append("</svg>")
        (OUT / (self.name + ".svg")).write_text("\n".join(self.items), encoding="utf-8")


def build():
    d = Diagram(
        "fig02-evidence",
        "02  研究线索如何成为可检查的设计",
        "每行是一条设计推导；文献机制与本项目的产品改编分别呈现。",
        830,
    )
    heads = ["研究／机制", "用户需要与要求", "策略／交互", "系统承接与观察"]
    for x, t in zip([48, 395, 742, 1089], heads):
        d.text(x, 140, t, 23, True)
    rows = [
        [
            ("压力来源多样", ["E01／E02", "混合压力与路径线索"]),
            ("保留未知", ["不靠单一词语选行动", "澄清最低必要信息"]),
            ("情境与意愿分开", ["可只倾诉；允许无匹配", "多标签不等于多项建议"]),
            ("Analysis → Catalog", ["来源与资格检查", "N01及混合情境回放"]),
        ],
        [
            ("求助障碍与尊重", ["E04／E05／E13", "隐私、评价与信任"]),
            ("自主控制", ["先询问；可拒绝", "联系人需具体判断"]),
            ("邀请与安全入口", ["安全表达／现实支持", "安静、撤回、退出"]),
            ("状态机＋输出闸门", ["拒绝立即生效", "许可与取消业务检查"]),
        ],
        [
            ("具体加工与小问题", ["E06／E08", "从笼统转向可操作片段"]),
            ("有限认知负担", ["一次一个焦点", "不要求立刻解决全部"]),
            ("S16三步改编", ["具体片段 → 可控一步", "短步骤需重新验证"]),
            ("Planner → Talker", ["当前步骤投影", "执行记录与质量审读"]),
        ],
        [
            ("证据层级与归因", ["设计／工程方法要求", "完成不等于收益"]),
            ("可追溯、可更正", ["事实、推测、反馈分开", "范围和时间不被扩大"]),
            ("四类来源记忆", ["明确反馈关联实际支持", "无反馈保留为缺失"]),
            ("Memory＋Store", ["supersedes／过期／清除", "来源及并发检查"]),
        ],
    ]
    for r, row in enumerate(rows):
        y = 165 + r * 151
        for c, (title, lines) in enumerate(row):
            x = 48 + c * 347
            d.box(x, y, 305, 125, title, lines, ["gray", "amber", "teal", "blue"][c])
            if c < 3:
                d.arrow([(x + 305, y + 62), (x + 340, y + 62)])
    d.save("设计转译的可追溯性已实现；用户效果尚需相应参与者研究。")

    d = Diagram(
        "fig03-system",
        "03  四条通路共享状态，但承担不同责任",
        "后台形成方向，前台组织当轮表达；状态与输出控制保留最终执行权。",
        920,
    )
    d.box(
        48, 135, 260, 140, "入口与用户", ["CLI／小智语音", "ASR文本、wake来源", "拒绝、反馈、清除"]
    )
    d.box(
        375,
        135,
        460,
        140,
        "实时 Core ＋ 状态机",
        [
            "输入索引、generation、许可与阶段",
            "冻结 TurnPolicyFrame 和相关记忆",
            "Talker只负责本轮受约束表达",
        ],
    )
    d.box(
        920,
        135,
        465,
        140,
        "输出控制与适配",
        ["OutputRail → 小智／CLI", "代次检查、分句、下一句预取", "started／completed事件"],
    )
    d.arrow([(308, 205), (375, 205)])
    d.arrow([(835, 205), (920, 205)])
    d.box(
        48,
        360,
        320,
        180,
        "独立安全通路",
        [
            "L1规则＋L2风险模型",
            "独立资源；不排认知队列",
            "high → 取消普通输出",
            "固定危机文本／音频",
        ],
        "red",
    )
    d.box(
        425,
        360,
        470,
        180,
        "后台 Cognition",
        [
            "触发与合并 → 每用户隔离／公平调度",
            "Analysis／Planner／Brief／Critic",
            "预算、deadline、失败与取消",
            "经 DeltaGuard＋CAS 发布策略",
        ],
        "blue",
    )
    d.box(
        950,
        360,
        435,
        180,
        "长期关系记忆",
        [
            "Memory／End整理候选",
            "来源、范围、时间、更正校验",
            "相关性检索＋主动提及限制",
            "持久化结束任务与重试",
        ],
        "purple",
    )
    d.arrow([(180, 275), (180, 360)])
    d.arrow([(605, 275), (605, 360)], True)
    d.arrow([(470, 360), (470, 315), (415, 315), (415, 275)], True)
    d.arrow([(1165, 360), (1165, 320), (805, 320), (805, 275)], True)
    d.arrow([(368, 450), (395, 450), (395, 300), (1397, 300), (1397, 205), (1385, 205)], True)
    d.box(
        48,
        650,
        1337,
        155,
        "Store ＋ InteractionEvent ＋ 观察台",
        [
            "SQLite事务与正式v1→v2迁移；策略版本、会话游标、输出关联与支持反馈分开保存",
            "四类记忆与supersedes；结束恢复；清除epoch阻止在途旧任务回写",
            "观察台展示触发、角色结果、评审、发布／拒绝原因、记忆范围和采用结果",
        ],
        "gray",
    )
    for x in [208, 660, 1165]:
        d.arrow([(x, 540), (x, 650)])
    d.save("实线：主要数据／执行流；虚线：异步结果或控制。所有模型调用经 Aihubmix。")

    d = Diagram(
        "fig04-content",
        "04  内容层次：原则、策略与脚本分别承担什么",
        "策略是有条件的可选内容；倾听、安静与拒绝本身是成立的互动结果。",
        870,
    )
    d.box(
        48,
        130,
        1337,
        92,
        "贯穿所有互动的原则",
        ["低评判、尊重意愿、准确表达、一次一个焦点；不把未知补成事实"],
        "gray",
    )
    cards = [
        ("S16  具体一步", ["反复想 → 具体片段", "可控的小步骤"]),
        ("kind_self_talk", ["苛责 → 准确温和表达", "不做积极保证"]),
        ("safe_communication", ["已有安全对象", "只练一句表达"]),
        ("safe_support", ["探索现实支持入口", "对象、渠道与透露范围"]),
        ("values_exploration", ["不确定方向", "小规模了解可靠信息"]),
        ("worry_parking", ["睡前暂存一个担忧", "留待合适时间处理"]),
    ]
    for i, (t, ls) in enumerate(cards):
        d.box(48 + (i % 3) * 451, 270 + (i // 3) * 155, 420, 125, t, ls)
    d.box(
        48,
        620,
        420,
        140,
        "三段确定性短练习",
        ["自然呼吸 36.25秒", "外部定向 33.7秒", "睡前暂停 29.9秒"],
        "amber",
    )
    d.box(
        499,
        620,
        420,
        140,
        "现实支持连接",
        ["safe_support探索入口", "safe_communication练表达", "双方均需检查安全与意愿"],
        "blue",
    )
    d.box(
        950,
        620,
        435,
        140,
        "独立风险响应",
        ["不作为普通策略候选", "high接入固定支持", "普通模型不能自行解除"],
        "red",
    )
    d.save("当前 course-1.0：六张策略卡＋三段练习；每次行动一张卡，每张卡每会话最多一次。")

    d = Diagram(
        "fig05-consent",
        "05  许可、行动与退出的关键状态",
        "评议通过只产生合格候选；用户控制仍由当前状态和输出事件决定。",
        780,
    )
    d.box(48, 160, 285, 140, "倾听／澄清", ["理解当前需求", "允许只说、不做", "可留在当前阶段"])
    d.box(
        395,
        160,
        300,
        140,
        "支持邀请",
        ["当前边界允许邀请", "邀请开始输出才激活", "pending offer"],
        "amber",
    )
    d.box(
        760,
        160,
        300,
        140,
        "明确同意",
        ["绑定有效邀请与当轮状态", "若候选未就绪，有界等待", "再次检查资格与版本"],
        "amber",
    )
    d.box(
        1120, 160, 270, 140, "行动／练习", ["一次一个焦点", "具体练习另需许可", "步数与时长有上限"]
    )
    for a, b in [(333, 395), (695, 760), (1060, 1120)]:
        d.arrow([(a, 230), (b, 230)])
    d.box(
        395,
        430,
        360,
        150,
        "拒绝／中止／话题边界",
        ["立即停止当前推进", "取消旧代次与预取", "记录拒绝；转倾听或安静"],
        "red",
    )
    d.box(
        850,
        430,
        450,
        150,
        "收尾、安静与再次互动",
        ["不把沉默当作同意", "真实wake来源参与重新唤醒", "新行动重新满足许可与资格"],
        "teal",
    )
    d.arrow([(540, 300), (540, 430)])
    d.arrow([(900, 300), (900, 355), (650, 355), (650, 430)])
    d.arrow([(1240, 300), (1240, 430)])
    d.arrow([(1120, 265), (1090, 265), (1090, 390), (710, 390), (710, 430)], True)
    d.arrow([(395, 505), (190, 505), (190, 300)])
    d.arrow([(850, 550), (800, 550), (800, 655), (95, 655), (95, 300)], True)
    d.save("邀请送达的当前证据是服务端started；没有逐段设备播放ACK，不能据此认定用户已经听到。")

    d = Diagram(
        "fig07-agents",
        "07  有限协作：routine 与 deliberation",
        "独立Brief看原始情境与边界，不读取Analysis结论、策略卡或Planner候选。",
        970,
    )
    d.text(48, 140, "ROUTINE · 非行动方向 · 2次基本调用", 23, True)
    for x, t, ls in [
        (48, "Analysis", ["事实、情境、意愿"]),
        (450, "Planner", ["倾听／澄清／安慰等"]),
        (900, "发布检查", ["不生成行动候选"]),
    ]:
        d.box(x, 165, 340, 105, t, ls, "blue")
    d.arrow([(388, 215), (450, 215)])
    d.arrow([(790, 215), (900, 215)])
    d.text(48, 330, "DELIBERATION · 完整评议 · 4次或6次基本调用", 23, True)
    d.box(48, 375, 300, 125, "Analysis", ["SituationAssessment", "情境、证据、必要条件"], "blue")
    d.box(48, 560, 300, 125, "独立 Brief", ["ReviewBrief", "用户需求与评议约束"], "blue")
    d.box(425, 375, 330, 125, "Planner V1", ["SupportPlan候选", "单一支持方向与条件"], "blue")
    d.box(835, 375, 330, 125, "Critic V1", ["核对候选ID与版本", "approve／revise／reject"], "blue")
    d.arrow([(348, 435), (425, 435)])
    d.arrow([(755, 435), (835, 435)])
    d.arrow([(348, 620), (795, 620), (795, 470), (835, 470)])
    d.box(425, 735, 330, 110, "Planner V2", ["仅一次修订"], "blue")
    d.box(835, 735, 330, 110, "Critic V2", ["修订后复核；不再循环"], "blue")
    d.arrow([(995, 500), (995, 660), (590, 660), (590, 735)])
    d.text(610, 649, "revise／本地冲突", 18)
    d.arrow([(755, 790), (835, 790)])
    d.arrow([(348, 650), (380, 650), (380, 895), (1010, 895), (1010, 845)])
    d.text(450, 885, "同一独立Brief继续用于修订后复核", 18)
    d.box(
        1225,
        375,
        170,
        470,
        "规则发布",
        [
            "批准后仍查",
            "来源与范围",
            "DeltaGuard",
            "最终CAS",
            "有效期／版本",
            "",
            "拒绝有原因",
            "不会自动执行",
        ],
        "amber",
    )
    d.arrow([(1165, 435), (1225, 435)])
    d.arrow([(1165, 790), (1225, 790)])
    d.text(1167, 420, "approve", 13)
    d.text(1167, 775, "approve", 13)
    d.save(
        "同一任务共享20秒deadline；routine最多4次、deliberation最多8次调用，含共享修复与最多一次DeltaGuard。"
    )

    d = Diagram(
        "fig08-memory",
        "08  带来源、范围与更正的记忆生命周期",
        "长期连续性来自可核实记录；模型推测与未提供的反馈不能自动变成长期事实。",
        840,
    )
    for x, t, ls, c in [
        (48, "来源证据", ["用户原话／交互事件", "明确偏好与边界", "实际支持及明确反馈"], "gray"),
        (
            395,
            "Memory／End候选",
            ["事实偏好、情境事件", "交互边界、支持经历", "与原会话游标绑定"],
            "purple",
        ),
        (
            742,
            "写入校验",
            ["来源ID与认识状态", "时间范围、主体与版本", "纠正和supersedes"],
            "purple",
        ),
        (1089, "Store事务", ["采用或拒绝原因", "清除epoch屏障", "旧来源不可覆盖新更正"], "purple"),
    ]:
        d.box(x, 155, 305, 165, t, ls, c)
    for x in [353, 700, 1047]:
        d.arrow([(x, 235), (x + 42, 235)])
    d.box(
        742,
        430,
        652,
        160,
        "读取投影：先过滤，再排序",
        [
            "用户隔离 → 有效状态／时间／范围 → 中文词面相关性",
            "重要性、近期与重复线索参与排序；边界单独纳入",
            "allowed／only_when_raised／avoid_proactive约束提及",
        ],
        "purple",
    )
    d.arrow([(1240, 320), (1240, 430)])
    d.box(
        48,
        430,
        605,
        160,
        "后续互动：使用与更新",
        [
            "Talker只读符合本轮情境的记忆投影",
            "“名字是小琳” → 更正小林，保留新旧来源",
            "“今天不谈学校”到期；不扩大为永久拒绝",
        ],
        "teal",
    )
    d.arrow([(742, 510), (653, 510)])
    d.arrow([(95, 430), (95, 320)], True)
    d.box(
        48,
        660,
        1346,
        90,
        "明确反馈与缺失反馈",
        [
            "支持执行完成只记录执行；有帮助／无帮助需用户表达并关联实际支持。一次负面反馈不永久定性。"
        ],
        "amber",
    )
    d.save("检索为中文二元片段／词面匹配，不是语义向量检索；图中姓名与边界均为合成示例。")

    d = Diagram(
        "fig09-validity",
        "09  新输入到来：按产物判断，不一律丢弃",
        "不同产物的使用时机与证据不同；最终状态通过事务中的比较交换（CAS）保护。",
        860,
    )
    d.box(
        48,
        130,
        1345,
        90,
        "新输入／纠正／取消",
        ["按事件更新输入游标／输出代次；下面四个分支分别判断有效性。"],
        "gray",
    )
    rows = [
        (
            "当轮输出／播放",
            ["旧generation立即失效", "未发送文本与预取音频停止"],
            "当前代次重新组织表达",
            "red",
        ),
        (
            "SupportPlan策略",
            ["检查时间、增量、来源及基准版本", "有新输入时最多一次DeltaGuard"],
            "最终CAS → 后续合法回合可采用",
            "blue",
        ),
        (
            "MemoryItem记忆",
            ["检查来源、范围、后续更正与清除epoch", "策略被拒不必连带丢弃有效记忆"],
            "合法候选可部分提交",
            "purple",
        ),
        (
            "End结束总结",
            ["绑定原会话和结束游标", "持久化任务、幂等恢复、来源更正"],
            "更新原会话；不能覆盖新事实",
            "purple",
        ),
    ]
    for i, (t, ls, result, c) in enumerate(rows):
        y = 260 + i * 130
        d.box(48, y, 320, 105, t, (), c)
        d.box(425, y, 565, 105, "独立检查", ls, c)
        d.box(1045, y, 348, 105, "采用结果", [result], c)
        d.arrow([(368, y + 53), (425, y + 53)])
        d.arrow([(990, y + 53), (1045, y + 53)])
    d.save("策略TTL从排队时刻计算，不因复核刷新；检查后又来新输入，CAS仍会拒绝过时发布。")

    d = Diagram(
        "fig10-control",
        "10  规则控制如何约束模型与输出",
        "风险、许可、版本与取消是执行条件；角色评审不能代替这些条件。",
        800,
    )
    d.box(
        48,
        150,
        370,
        170,
        "独立风险 L1／L2",
        [
            "与普通认知任务资源隔离",
            "输入起算的有界输出闸门",
            "迟到high仍可接管",
            "high不能被普通模型解除",
        ],
        "red",
    )
    d.box(
        535,
        150,
        370,
        170,
        "用户许可与边界",
        [
            "邀请激活＋明确同意",
            "拒绝／中止先于继续行动",
            "边界变化即时影响本轮",
            "Critic批准不授予许可",
        ],
        "amber",
    )
    d.box(
        1025,
        150,
        370,
        170,
        "版本与generation",
        [
            "候选经最终发布检查",
            "TurnPolicyFrame冻结当轮",
            "旧代次输出／预取失效",
            "每次发送仍检查当前代次",
        ],
        "blue",
    )
    d.box(
        535, 430, 370, 125, "普通输出闸门", ["所有当前执行条件成立", "Talker或确定性步骤"], "teal"
    )
    d.arrow([(720, 320), (720, 430)])
    d.arrow([(1210, 320), (1210, 390), (875, 390), (875, 430)])
    d.arrow([(418, 255), (475, 255), (475, 490), (535, 490)])
    d.text(380, 370, "风险状态", 19)
    d.box(48, 600, 370, 110, "固定危机支持", ["取消普通输出并接管音频"], "red")
    d.box(1025, 600, 370, 110, "适配器发送", ["小智／CLI：按当前代次执行"], "teal")
    d.arrow([(233, 320), (233, 600)])
    d.arrow([(905, 490), (1210, 490), (1210, 600)])
    d.arrow([(418, 655), (1025, 655)])
    d.text(475, 638, "high取消普通代次；固定内容也遵守输出控制", 19)
    d.save("闸门是有界等待：尚未判为high的内容可能先放行，迟到风险接管不能撤回已发出的内容。")

    d = Diagram(
        "fig11-audio",
        "11  语音流水：当前句发送时准备下一句",
        "当前实现仍需等待完整WAV；有界下一句预取主要减少后续句间等待。",
        820,
    )
    d.text(48, 145, "当前句", 22, True)
    stages = [
        ("Talker分句", ["得到可发声文本"]),
        ("动态TTS", ["完整WAV返回"]),
        ("Opus编码", ["首包ready"]),
        ("代次检查＋发送", ["首包sent／client收到"]),
    ]
    for i, (t, ls) in enumerate(stages):
        x = 48 + i * 347
        d.box(x, 175, 305, 105, t, ls)
        if i < 3:
            d.arrow([(x + 305, 228), (x + 347, 228)])
    d.text(48, 345, "下一句", 22, True)
    d.box(
        395,
        375,
        652,
        120,
        "最多预取下一句：准备与当前句发送重叠",
        [
            "2个语音槽；按句序消费；generation变化即取消",
            "已开始的外部调用可能仍占槽，完成后结果也不得发送",
        ],
        "blue",
    )
    d.arrow([(1100, 280), (1100, 335), (720, 335), (720, 375)], True)
    d.box(
        48, 580, 420, 125, "固定音频接管", ["缓存危机／练习片段", "绕过动态TTS，不绕过取消"], "red"
    )
    d.box(
        535,
        580,
        400,
        125,
        "输出事件",
        ["started／completed／cancelled", "与支持ID、版本和步骤关联"],
        "amber",
    )
    d.box(
        1000,
        580,
        395,
        125,
        "用户后续表达",
        ["明确反馈 → 支持经历候选", "没有反馈 → 不推断有效"],
        "purple",
    )
    d.arrow([(468, 640), (535, 640)])
    d.arrow([(935, 640), (1000, 640)])
    d.arrow([(1240, 280), (1410, 280), (1410, 535), (735, 535), (735, 580)])
    d.save(
        "测量分别记录首token、首句、TTS、编码、发送及客户端接收；服务端completed不是设备播放ACK。"
    )

    # Standard plotting library keeps quantitative axes, labels and SVG editable.
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        plt.rcParams["font.family"] = ["Noto Sans CJK SC", "sans-serif"]
    plt.rcParams.update(
        {
            "svg.fonttype": "none",
            "svg.hashsalt": "companion-research-design",
            "font.size": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    data = {
        "batch": "voice-final2",
        "unit": "seconds",
        "foreground_n": 30,
        "background_n": 8,
        "labels": ["文本首句／闸门放行", "客户端首包接收", "后台任务执行"],
        "p50": [1.2575, 3.609, 12.6107],
        "p90": [1.421, 4.015, 15.3163],
    }
    (ROOT / "sources/performance.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fig, axs = plt.subplots(
        1, 2, figsize=(14.4, 6.5), gridspec_kw={"width_ratios": [1.3, 1]}, layout="constrained"
    )
    fig.get_layout_engine().set(h_pad=0.18, w_pad=0.18)
    fig.set_facecolor("#fbfaf6")
    for ax in axs:
        ax.set_facecolor("#fbfaf6")
        ax.grid(axis="x", alpha=0.18)
        ax.set_axisbelow(True)
    for ax, ids in [(axs[0], [0, 1]), (axs[1], [2])]:
        for j, i in enumerate(ids):
            ax.barh(
                j + 0.16,
                data["p50"][i],
                0.28,
                color=COLORS["teal"],
                label="P50" if j == 0 else None,
            )
            ax.barh(
                j - 0.16,
                data["p90"][i],
                0.28,
                color=COLORS["blue"],
                label="P90" if j == 0 else None,
            )
            for dy, key in [(0.16, "p50"), (-0.16, "p90")]:
                ax.text(
                    data[key][i] + 0.06, j + dy, f"{data[key][i]:.3f}", va="center", fontsize=11
                )
        ax.set_yticks(range(len(ids)), [data["labels"][i] for i in ids])
        ax.invert_yaxis()
        ax.set_xlabel("秒")
        ax.legend(loc="lower right")
    axs[0].set_xlim(0, 5.2)
    axs[0].set_ylim(1.7, -0.6)
    axs[0].axvline(0.9, color=COLORS["amber"], ls="--")
    axs[0].text(0.95, 1.48, "文本首句目标 0.9秒", color=COLORS["amber"], fontsize=11)
    axs[0].set_title("普通动态语音 · n=30", loc="left", pad=18)
    axs[1].set_xlim(0, 19)
    axs[1].set_ylim(0.8, -0.6)
    axs[1].axvline(8, color=COLORS["amber"], ls="--")
    axs[1].text(8.3, 0.6, "常规后台期望 8秒", color=COLORS["amber"], fontsize=11)
    axs[1].set_title("后台任务 · n=8", loc="left", pad=18)
    fig.suptitle("13  当前性能：有限样本与未达目标", fontsize=21, x=0.02, ha="left")
    fig.supxlabel(
        "历史最终批次；前台为经验分位数，后台为插值分位数。真机首响未测；两面板横轴尺度不同。",
        fontsize=11,
    )
    fig.savefig(OUT / "fig13-performance.svg", metadata={"Date": None})
    plt.close(fig)
    svg = OUT / "fig13-performance.svg"
    svg.write_text(
        "\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    os.environ.setdefault(
        "MPLCONFIGDIR", str(ROOT.parents[2] / "artifacts/research-design/matplotlib")
    )
    build()
