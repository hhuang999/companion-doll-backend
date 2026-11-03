from companion.adapters.xiaozhi.runtime import get_core
from core.providers.llm.base import LLMProviderBase


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.companion_core = get_core(config)

    def response(self, session_id, dialogue, **kwargs):
        raise RuntimeError("Companion requires the receiveAudioHandle registration patch")
