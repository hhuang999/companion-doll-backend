"""Output drivers share generation checks and playback acknowledgements."""

import logging
import queue
import threading
import time
from collections.abc import Callable

from companion.core.models import OutputEvent, PlaybackEvent


class RecordingOutputPort:
    """In-memory port used by offline scenarios and integration test doubles."""

    def __init__(
        self, callback: Callable[[PlaybackEvent], None], auto_complete: bool = True
    ) -> None:
        self.callback = callback
        self.auto_complete = auto_complete
        self.events: list[OutputEvent] = []
        self.minimum: dict[str, int] = {}
        self.seen: set[str] = set()
        self.lock = threading.RLock()

    def valid(self, event: OutputEvent) -> bool:
        with self.lock:
            return event.generation >= self.minimum.get(event.session_id, 0)

    def cancel_before(self, session_id: str, generation: int) -> None:
        with self.lock:
            self.minimum[session_id] = max(generation, self.minimum.get(session_id, 0))

    def acknowledge(self, event: OutputEvent, status: str, **fields: object) -> None:
        self.callback(
            PlaybackEvent(
                output_id=event.output_id,
                session_id=event.session_id,
                generation=event.generation,
                status=status,
                **fields,
            )
        )

    def submit(self, event: OutputEvent) -> None:
        with self.lock:
            if not self.valid(event) or event.output_id in self.seen:
                return
            self.seen.add(event.output_id)
            self.events.append(event)
        self.acknowledge(event, "started")
        if self.auto_complete:
            self.acknowledge(event, "completed")


class ConsoleOutputPort(RecordingOutputPort):
    def __init__(
        self,
        callback: Callable[[PlaybackEvent], None],
        *,
        realtime: bool = False,
        render: Callable[[str], None] = print,
    ) -> None:
        super().__init__(callback, auto_complete=False)
        self.realtime = realtime
        self.render = render
        self.queue: queue.Queue[OutputEvent | None] = queue.Queue()
        self.worker = threading.Thread(target=self._run, name="console-output", daemon=True)
        self.worker.start()

    def submit(self, event: OutputEvent) -> None:
        with self.lock:
            if not self.valid(event) or event.output_id in self.seen:
                return
            self.seen.add(event.output_id)
            self.events.append(event)
            self.queue.put(event)

    def _run(self) -> None:
        while True:
            event = self.queue.get()
            try:
                if event is None:
                    return
                if not self.valid(event):
                    self.acknowledge(event, "cancelled")
                    continue
                self.acknowledge(event, "started")
                if event.plan:
                    for index, segment in enumerate(
                        event.plan.segments[event.plan.start_index :], event.plan.start_index
                    ):
                        if not self.valid(event):
                            break
                        self.acknowledge(event, "segment", segment_index=index)
                        self.render(f"{event.emoji} {segment.text}")
                        if self.realtime:
                            end = time.monotonic() + segment.pause_s
                            while self.valid(event) and time.monotonic() < end:
                                time.sleep(min(0.05, max(0, end - time.monotonic())))
                else:
                    self.render(f"{event.emoji} {event.text}")
                self.acknowledge(event, "completed" if self.valid(event) else "cancelled")
            except Exception as error:
                logging.getLogger(__name__).exception("Console output failed")
                if event:
                    self.acknowledge(event, "failed", error=type(error).__name__)
            finally:
                self.queue.task_done()

    def wait_idle(self) -> None:
        self.queue.join()

    def close(self) -> None:
        self.queue.put(None)
        self.worker.join(timeout=5)
