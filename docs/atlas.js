const modules = {
  overview: ['模块总图', '22 个模块与依赖关系。先看核心的控制权，再沿输入、分析和输出路径展开。'],
  turn: ['实时回复', '从输入去重、固定轮次上下文，到提示词、流式分句、输出校验、闸门和播放提交。'],
  consent: ['状态与许可', '提议何时激活，同意如何保留，卡片如何筛选，以及行动、安静与练习之间的转换。'],
  risk: ['风险接管', '本地词表与独立模型并行工作，区分 600 ms 输出等待、2.5 s 检测预算和迟到 high 接管。'],
  reasoner: ['后台分析', '同用户串行调度 → 来源与业务校验 → 过期检查 → 事务提交 → 下轮应用新快照。'],
  audio: ['语音链路', '小智六处补丁、线程与协程、固定缓存、动态合成、Opus 转码，以及独立取消与回执。'],
  data: ['数据与恢复', '12 张表的职责、结构化记忆读写、跟进预留、结束任务，以及进程恢复和数据清除。'],
};

const frame = document.querySelector('#diagram');
const description = document.querySelector('#description');
const standalone = document.querySelector('#standalone');

function selectModule() {
  const requested = location.hash.slice(1);
  const slug = Object.hasOwn(modules, requested) ? requested : 'overview';
  const [label, summary] = modules[slug];
  document.querySelectorAll('nav a').forEach(link => {
    if (link.dataset.module === slug) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  });
  description.textContent = summary;
  standalone.href = `diagrams/${slug}.html`;
  frame.title = `${label}：可交互架构图与设计说明`;
  if (frame.dataset.module !== slug) {
    frame.dataset.module = slug;
    frame.src = `diagrams/${slug}.html`;
  }
  document.title = `${label} · 情感陪伴玩偶后端设计`;
}

document.querySelectorAll('nav a').forEach(link => {
  link.addEventListener('click', event => {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    location.hash = link.dataset.module;
  });
});
window.addEventListener('hashchange', selectModule);
selectModule();
