"use strict";

const $ = (selector) => document.querySelector(selector);
const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const labels = {
  academic: "学业",
  social_evaluative: "社会评价",
  relationship: "关系",
  future: "未来",
  self: "自我压力",
  rumination: "反复想",
  self_criticism: "自我批评",
  sleep: "睡眠",
  loneliness: "孤独",
};
const contexts = {
  unsafe_relationship: "关系不安全",
  no_private_space: "缺少隐私",
  bedtime: "睡前",
  limited_time: "时间有限",
  body_focus_distress: "身体关注引发不适",
  safe_contact: "已确认相对安全的联系人",
};
const sourceBase = "https://github.com/hhuang999/companion-doll-backend/blob/";
const list = (items, ordered = false) => {
  const node = element(ordered ? "ol" : "ul");
  items.forEach((text) => node.append(element("li", text)));
  return node;
};

// Preset teaching examples explain code responsibilities, never impersonate a live model.
const scenarios = {
  listen: {
    user: "今天考得不太好。我只想说说，先别给建议。",
    reply: "好，先听你说。",
    mode: "routine / 非行动支持",
    steps: [
      ["理解当下需要", "明确想被听见，不追问解决办法。"],
      ["尊重行动边界", "目录过滤排除行动支持，保留倾听。"],
      ["按范围记住", "记录当前边界，不推断永久偏好。"],
    ],
    result: "结果：倾听本身就是这次支持，不需要进入行动。",
  },
  action: {
    user: "我总在想今天没做好的那道题。能陪我找一个小办法吗？",
    reply: "要不要一起只看这一小处，找一件你能影响的事？",
    mode: "deliberation / 等待明确许可",
    steps: [
      ["理解与筛选", "分析学业压力与反复想；先核对意愿、情境和排除条件。"],
      [
        "独立评议候选",
        "Brief 独立读取证据；Planner 提议具体一步，Critic 复核，最多修订一次。",
      ],
      [
        "邀请与执行分开",
        "示例假设候选已通过评审及版本校验。发出邀请后，仍等待明确同意。",
      ],
    ],
    result: "轮到你决定：可以同意，也可以随时拒绝。",
  },
  feedback: {
    user: "刚才这个办法没帮助。我现在只想有人听。",
    reply: "好，先停下这个办法。我听你说。",
    mode: "反馈归因 / 停止当前行动",
    steps: [
      [
        "先停下当前行动",
        "合成前提：本会话刚执行过一项支持。收到拒绝，取消旧输出与待执行内容。",
      ],
      [
        "记录具体反馈",
        "关联这次支持的 ID、版本、步骤与用户原话；不能只凭播放完成判断效果。",
      ],
      [
        "调整后续支持",
        "本会话不重复同一方法。后续使用先检查范围；一次无效不是永久偏好。",
      ],
    ],
    result: "结果：后续支持因明确反馈而改变，倾听继续。",
  },
};

function initDemo() {
  let current = "listen";
  let timer = null;
  let step = -1;
  let running = false;
  let settled = false;
  const play = $("#demo-play");
  const actions = $("#demo-actions");
  function stop() {
    window.clearTimeout(timer);
    timer = null;
    running = false;
  }
  function setPlayLabel(text) {
    play.querySelector("span").textContent = text;
  }
  function showScenario(name, animate = false) {
    stop();
    current = name;
    step = -1;
    settled = false;
    const data = scenarios[name];
    document
      .querySelectorAll("[data-scenario]")
      .forEach((button) =>
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.scenario === name),
        ),
      );
    $("#demo-user").textContent = data.user;
    $("#demo-reply").textContent = data.reply;
    $("#demo-mode").textContent = data.mode;
    $("#decision-path").replaceChildren(
      ...data.steps.map(([title, text]) => {
        const row = element("li");
        const dot = element("span", undefined, "path-dot");
        dot.setAttribute("aria-hidden", "true");
        const content = element("div");
        content.append(element("b", title), element("p", text));
        row.append(dot, content);
        return row;
      }),
    );
    actions.hidden = name !== "action";
    $("#demo-status").textContent = data.result;
    setPlayLabel("演示判断过程");
    $("#dialogue-content").classList.remove("switched");
    if (animate && !reducedMotion.matches) {
      // Restart only on an explicit pointer change, never on keyboard navigation.
      void $("#dialogue-content").offsetWidth;
      $("#dialogue-content").classList.add("switched");
    }
  }
  function next() {
    step += 1;
    const rows = [...$("#decision-path").children];
    rows.forEach((row, index) => row.classList.toggle("active", index <= step));
    if (step < rows.length) {
      $("#demo-status").textContent =
        `${step + 1} / ${rows.length} · ${scenarios[current].steps[step][0]}`;
      timer = window.setTimeout(next, 1050);
    } else {
      stop();
      $("#demo-status").textContent = scenarios[current].result;
      actions.hidden = current !== "action" || settled;
      setPlayLabel("再看一次过程");
    }
  }
  document
    .querySelectorAll("[data-scenario]")
    .forEach((button) =>
      button.addEventListener("click", (event) =>
        showScenario(button.dataset.scenario, event.detail > 0),
      ),
    );
  play.addEventListener("click", () => {
    if (running) {
      stop();
      setPlayLabel("继续演示");
      $("#demo-status").textContent = "演示已暂停，可以继续或切换情境。";
      return;
    }
    if (settled) showScenario(current);
    if (reducedMotion.matches) {
      $("#decision-path")
        .querySelectorAll("li")
        .forEach((row) => row.classList.add("active"));
      $("#demo-status").textContent = scenarios[current].result;
      actions.hidden = current !== "action";
      setPlayLabel("再次查看判断");
      return;
    }
    if (step >= scenarios[current].steps.length) step = -1;
    running = true;
    actions.hidden = true;
    setPlayLabel("暂停演示");
    next();
  });
  $("#demo-reset").addEventListener("click", () => showScenario(current));
  function decide(yes) {
    stop();
    settled = true;
    actions.hidden = true;
    $("#demo-reply").textContent = yes
      ? "只看那道题的话，你想先弄清卡在哪一步，还是先说说想到它时的感受？"
      : "好，先不安排办法。";
    $("#demo-mode").textContent = yes
      ? "明确许可 / 执行当前一步"
      : "撤回邀请 / 保留倾听";
    const last = $("#decision-path").lastElementChild;
    last.querySelector("b").textContent = yes
      ? "许可有效，执行当前一步"
      : "拒绝生效，停止行动";
    last.querySelector("p").textContent = yes
      ? "示例中许可绑定当前提议；Talker 只执行这一焦点，用户仍可中止。"
      : "清除待执行提议。没有同意，也能完成一次支持。";
    $("#decision-path")
      .querySelectorAll("li")
      .forEach((row) => row.classList.add("active"));
    $("#demo-status").textContent = yes
      ? "你选择了尝试。重新开始可比较拒绝后的路径。"
      : "你选择了暂不行动。重新开始可比较同意后的路径。";
    setPlayLabel("重新演示邀请");
    play.focus({ preventScroll: true });
  }
  $("#consent-yes").addEventListener("click", () => decide(true));
  $("#consent-no").addEventListener("click", () => decide(false));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && running) {
      stop();
      setPlayLabel("继续演示");
      $("#demo-status").textContent = "页面离开时已暂停演示。";
    }
  });
  showScenario("listen");
}

function initLatency() {
  // Source: VALIDATION.md, voice-final2. Each column is a cumulative percentile.
  const metrics = { p50: [1257.5, 3539, 3609], p90: [1421, 3937, 4015] };
  const seconds = (milliseconds) =>
    (Math.round(milliseconds / 10) / 100).toFixed(2);
  document.querySelectorAll("[data-percentile]").forEach((button) =>
    button.addEventListener("click", () => {
      document
        .querySelectorAll("[data-percentile]")
        .forEach((item) =>
          item.setAttribute("aria-pressed", String(item === button)),
        );
      const [text, tts, wire] = metrics[button.dataset.percentile];
      $("#latency-total").replaceChildren(
        document.createTextNode(seconds(wire)),
        element("span", "秒"),
      );
      $("#latency-text").textContent = `${seconds(text)} s`;
      $("#latency-tts").textContent = `${seconds(tts)} s`;
      $("#latency-wire").textContent = `${seconds(wire)} s`;
      $("#time-text").style.width = `${(text / wire) * 100}%`;
      $("#time-tts").style.width = `${((tts - text) / wire) * 100}%`;
      $("#time-wire").style.width = `${((wire - tts) / wire) * 100}%`;
    }),
  );
}

async function loadCatalog() {
  $("#catalog-status").textContent = "正在读取版本化策略目录…";
  try {
    const response = await fetch("assets/project-data.json");
    if (!response.ok) throw new Error(`内容目录 HTTP ${response.status}`);
    const data = await response.json();
    if (
      !Array.isArray(data.cards) ||
      !Array.isArray(data.sources) ||
      !Array.isArray(data.exercises) ||
      !/^[a-f0-9]{40}$/.test(data.revision)
    )
      throw new Error("内容目录结构不完整");
    document.querySelectorAll("[data-source]").forEach((link) => {
      link.href = sourceBase + data.revision + "/" + link.dataset.source;
    });
    $("#revision").textContent = data.revision.slice(0, 12);
    $("#revision").href =
      "https://github.com/hhuang999/companion-doll-backend/tree/" +
      data.revision;
    $("#content-version").textContent = data.catalog_version;
    const sources = new Map(data.sources.map((source) => [source.id, source]));
    function render() {
      const pressure = $("#pressure").value,
        pathway = $("#pathway").value,
        intent = $("#intent").value;
      const cards = data.cards.filter(
        (card) =>
          (!pressure || card.targets.pressure_types.includes(pressure)) &&
          (!pathway || card.targets.pathways.includes(pathway)),
      );
      $("#catalog").replaceChildren();
      if (intent !== "explore" || cards.length === 0) {
        const empty = element("div", undefined, "empty");
        empty.append(
          element(
            "h3",
            intent === "quiet"
              ? "可以就停在这里。"
              : intent === "listen"
                ? "先听你说，不安排办法。"
                : "这个组合没有直接映射的策略。",
          ),
          element(
            "p",
            intent === "explore"
              ? "实际运行会保留倾听，或只澄清必要信息；不会为了命中目录忽略适用条件。可以重置筛选，查看全部内容。"
              : "尊重当下的意愿，无需完成练习或作出行动承诺。",
          ),
        );
        $("#catalog").append(empty);
      } else
        cards.forEach((card) => {
          const details = element("details", undefined, "strategy");
          const summary = element("summary");
          const heading = element("div");
          heading.append(
            element("h3", card.name),
            element(
              "p",
              [...card.targets.pressure_types, ...card.targets.pathways]
                .map((key) => labels[key] || key)
                .join(" · "),
              "labels",
            ),
          );
          summary.append(
            element(
              "span",
              String(data.cards.indexOf(card) + 1).padStart(2, "0"),
              "strategy-index",
            ),
            heading,
            element("p", card.protocol.mechanism, "mechanism"),
          );
          const body = element("div", undefined, "strategy-body");
          const before = element("div");
          before.append(
            element("h4", "开始之前"),
            list(card.protocol.prerequisites),
          );
          if (card.protocol.required_contexts.length)
            before.append(
              element(
                "p",
                "必要情境：" +
                  card.protocol.required_contexts
                    .map((key) => contexts[key] || key)
                    .join("、"),
              ),
            );
          const steps = element("div");
          steps.append(
            element("h4", "具体怎么做"),
            list(card.steps, true),
            element("p", card.examples[0], "example"),
          );
          const avoid = element("div");
          avoid.append(element("h4", "什么时候不做"), list(card.not_when));
          const exit = element("div");
          exit.append(
            element("h4", "退出与反馈"),
            element("p", card.protocol.stop),
            element("p", card.protocol.feedback_limits),
          );
          const links = element("div", undefined, "source-links");
          links.append(
            element("span", card.id + " / " + card.protocol.version),
          );
          card.protocol.evidence_ids.forEach((id) => {
            const source = sources.get(id);
            if (source) {
              const link = element("a", id);
              link.href = source.url;
              links.append(link);
            }
          });
          const code = element("a", "配置源码");
          code.href = sourceBase + data.revision + "/" + card.path;
          links.append(code);
          body.append(before, steps, avoid, exit, links);
          details.append(summary, body);
          $("#catalog").append(details);
        });
      $("#catalog-status").textContent =
        intent === "explore"
          ? `${cards.length} / ${data.cards.length} 项内容映射 · 展开查看步骤、适用条件与退出`
          : "当前意愿不进入行动目录";
    }
    ["pressure", "pathway", "intent"].forEach((id) => {
      $("#" + id).onchange = render;
    });
    $("#reset").onclick = () => {
      $("#pressure").value = "";
      $("#pathway").value = "";
      $("#intent").value = "explore";
      render();
    };
    render();
    $("#exercises").replaceChildren(
      ...data.exercises.map((item) => {
        const article = element("article");
        article.append(
          element("h3", item.name),
          element("p", item.protocol.goal),
          element("p", item.protocol.invitation),
          list(item.protocol.prerequisites),
        );
        return article;
      }),
    );
    $("#source-list").replaceChildren(
      ...data.sources.map((source) => {
        const article = element("article", undefined, "source-entry");
        const title = source.citation
          .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
          .replace(/\*\*/g, "");
        const link = element("a", source.id + " · " + title);
        link.href = source.url;
        article.append(
          link,
          element("p", source.supports),
          element(
            "p",
            `实际读取：${source.read_scope} · 核查日期：${source.checked_on}`,
          ),
        );
        return article;
      }),
    );
    document.documentElement.dataset.ready = "true";
  } catch (error) {
    console.error("策略目录加载失败", error);
    $("#catalog-status").textContent =
      "策略目录加载失败。可重试，或通过下方 GitHub 链接阅读完整配置。";
    const retry = element("button", "重新加载目录", "button outline");
    retry.type = "button";
    retry.addEventListener("click", () => {
      retry.disabled = true;
      loadCatalog();
    });
    $("#catalog").replaceChildren(retry);
    $("#source-list").replaceChildren(
      element("p", "来源目录未加载；请使用上方完整核查链接。"),
    );
    document.documentElement.dataset.ready = "error";
  }
}

initDemo();
initLatency();
$("#copy-command").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText("./scripts/run.ps1 fake");
    $("#copy-status").textContent = "已复制离线启动命令。";
  } catch {
    $("#copy-status").textContent =
      "浏览器未允许复制，请选择上方命令手动复制。";
  }
});
loadCatalog();
