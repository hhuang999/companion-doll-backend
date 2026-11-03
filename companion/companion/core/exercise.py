from .config import Config
from .models import PlaybackPlan


class ExercisePlayer:
    def __init__(self, config: Config) -> None:
        self.config = config

    def build_plan(self, script_id: str, start_index: int = 0) -> PlaybackPlan:
        script = self.config.exercises[script_id]
        measured = all(
            line.audio_path and line.audio_duration_s is not None for line in script.lines
        )
        total = sum(line.pause_s + (line.audio_duration_s or 0) for line in script.lines)
        if total > self.config.settings.timing.exercise_max_s:
            raise ValueError("Exercise exceeds configured duration")
        if not 0 <= start_index < len(script.lines):
            raise ValueError("Invalid exercise resume index")
        return PlaybackPlan(
            script_id=script_id,
            segments=tuple(
                line.model_copy(
                    update={"audio_path": str((self.config.directory / line.audio_path).resolve())}
                )
                if line.audio_path
                else line
                for line in script.lines
            ),
            start_index=start_index,
            measured=measured,
        )
