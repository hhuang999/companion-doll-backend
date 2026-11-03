"""Risk work outlives the response generator and always retains input identity."""

import json
import logging
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from companion.llm.client import LLMClient

from .config import Config
from .models import RiskResult

logger = logging.getLogger(__name__)


class RiskDetector:
    def __init__(self, config: Config, llm: LLMClient) -> None:
        self.config = config
        self.llm = llm
        self.pool = ThreadPoolExecutor(
            max_workers=config.settings.pools.risk_workers, thread_name_prefix="risk"
        )
        self.patterns = {
            level: [
                (item["category"], re.compile(item["pattern"])) for item in config.lexicon[level]
            ]
            for level in ("high", "watch")
        }
        self.prompt = (config.directory / "prompts/risk.j2").read_text(encoding="utf-8")
        self.lock = threading.Lock()
        self.timers: set[threading.Timer] = set()
        self.futures: set[Future] = set()

    def lexicon(self, text: str) -> RiskResult:
        for level in ("high", "watch"):
            for category, pattern in self.patterns[level]:
                if pattern.search(text):
                    return RiskResult(level=level, category=category, reason=pattern.pattern)
        return RiskResult()

    def classify(
        self,
        text: str,
        context: list[str],
        callback: Callable[[RiskResult, float], None],
        usage_callback=None,
    ) -> Future:
        started = time.monotonic()
        deadline = started + self.config.settings.timing.risk_total_timeout_ms / 1000
        finished = threading.Event()
        notification_lock = threading.RLock()

        def notify(result: RiskResult) -> None:
            try:
                with notification_lock:
                    callback(result, (time.monotonic() - started) * 1000)
            except Exception:
                logger.exception("Risk callback failed")

        def timeout() -> None:
            with notification_lock:
                if not finished.is_set():
                    notify(
                        RiskResult(
                            level="watch", source="model", status="timeout", reason="risk_deadline"
                        )
                    )

        timer = threading.Timer(max(0, deadline - started), timeout)
        timer.daemon = True

        def run() -> RiskResult:
            try:
                result = self.llm.complete_json(
                    self.config.settings.llm.risk_model,
                    [
                        {"role": "system", "content": self.prompt},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {"context": context, "text": text}, ensure_ascii=False
                            ),
                        },
                    ],
                    RiskResult,
                    deadline,
                    temperature=0,
                    max_tokens=180,
                    accept_late_high=True,
                    usage_callback=usage_callback,
                )
                result = result.model_copy(update={"source": "model"})
            except Exception as error:
                logger.exception("Risk classification failed: %s", type(error).__name__)
                result = RiskResult(
                    level="watch",
                    source="model",
                    status="timeout" if isinstance(error, TimeoutError) else "error",
                    reason=type(error).__name__,
                )
            finally:
                finished.set()
                timer.cancel()
                with self.lock:
                    self.timers.discard(timer)
            notify(result)
            return result

        with self.lock:
            self.timers.add(timer)
            future = self.pool.submit(run)
            self.futures.add(future)
        future.add_done_callback(self._completed)
        timer.start()
        return future

    def _completed(self, future: Future) -> None:
        with self.lock:
            self.futures.discard(future)

    def wait_idle(self, timeout: float = 5) -> bool:
        from concurrent.futures import wait

        with self.lock:
            futures = list(self.futures)
        return not wait(futures, timeout=timeout).not_done if futures else True

    def close(self) -> None:
        self.pool.shutdown(wait=True, cancel_futures=False)
        with self.lock:
            for timer in self.timers:
                timer.cancel()
            self.timers.clear()
