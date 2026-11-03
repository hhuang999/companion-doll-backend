from companion.adapters.xiaozhi.runtime import get_core
from core.providers.memory.base import MemoryProviderBase


class MemoryProvider(MemoryProviderBase):
    def __init__(self, config, summary_memory=None):
        super().__init__(config)
        self.companion_core = get_core(config)

    async def query_memory(self, query):
        return ""

    async def save_memory(self, msgs, session_id=None):
        if session_id:
            self.companion_core.on_session_end(session_id, "disconnect")
