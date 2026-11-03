"""Finite role calls with independent contexts, shared budgets and observable usage."""

import hashlib
import json
import threading
import time

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from openai import APITimeoutError
from pydantic import ValidationError

from companion.memory.service import estimate_tokens

from .base import utcnow
from .models import Usage


class Agents:
    def __init__(self, config, store, llm):
        self.config, self.store, self.llm = config, store, llm
        self.slots = threading.BoundedSemaphore(config.settings.cognition.model_workers)
        self.templates = Environment(
            loader=FileSystemLoader(config.directory / "prompts"),
            undefined=StrictUndefined,
            autoescape=False,
        )

    def call(self, job, role, schema, payload, budget, *, candidate_version=None):
        config = self.config.settings.cognition
        model = getattr(config, f"{role}_model")
        output_limit = {
            "analysis": 900,
            "brief": 350,
            "planner": 900,
            "critic": 650,
            "delta": 350,
            "memory": 1800,
            "end": 1800,
        }[role]
        role_schema = compact_schema(schema.model_json_schema())
        if role == "analysis":
            # Keep the persisted contract backward compatible. Online assessment
            # does routing; explicit boundaries and dedicated consolidation own memory.
            for field in ("memory_candidates", "boundary_candidates"):
                role_schema["properties"].pop(field, None)
            role_schema = reachable_schema(role_schema)
        sources = {
            "user_turn": [row["id"] for row in payload.get("history", []) if row["role"] == "user"]
            + [row["id"] for row in payload.get("new_turns", [])],
            "memory": [item["memory_id"] for item in payload.get("memory", [])],
            "interaction_event": [item["event_id"] for item in payload.get("feedback", [])],
        }
        reference = role_schema.get("$defs", {}).get("EvidenceRef")
        if reference and any(sources.values()):
            reference["properties"]["kind"] = {
                "enum": [kind for kind, ids in sources.items() if ids]
            }
            reference["properties"]["id"] = {
                "enum": [identifier for ids in sources.values() for identifier in ids]
            }
        if role == "analysis":
            # Routing fields are optional for persisted legacy records, but every new
            # assessment must actually classify them rather than omit all defaults.
            role_schema["required"] = list(
                dict.fromkeys(
                    [
                        *role_schema.get("required", []),
                        "expressed_need",
                        "pressure_types",
                        "pathway_signals",
                        "emotion_intensity",
                        "readiness",
                        "support_constraints",
                    ]
                )
            )
        prompt = self.templates.get_template(f"{role}.j2").render(
            schema=json.dumps(
                role_schema,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        messages = [
            {
                "role": "system",
                "content": "Return only a JSON object matching this schema. Omit optional fields unless needed.\n"
                "每条引用必须同时填写kind、id、claim；claim是简短的依据说明，不能省略。"
                "evidence、source_refs、concerns、facts字段必须是JSON数组，即使只有一项。"
                "事实结构为{statement:文本,evidence:[{kind:来源类型,id:真实来源ID,claim:依据说明}]}。"
                "只有hypotheses中的对象允许conflicting_evidence。不要复制schema或示意占位内容。"
                "时间未知则省略；提供时间必须是带时区的ISO格式。\n" + prompt,
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        for attempt in range(1, 3):
            budget.check()
            if not self.slots.acquire(timeout=max(0, budget.deadline - time.monotonic())):
                raise TimeoutError("Background model slot deadline exceeded")
            start = time.monotonic()
            timestamp = utcnow().isoformat()
            estimated_input = estimate_tokens(messages)
            usage = Usage(
                input_tokens=estimated_input, output_tokens=output_limit, source="estimated"
            )
            reserved = False
            reserved_output = output_limit
            usage_values = []
            error = None
            result = None
            status = "failed"
            try:
                reserved_output = budget.reserve(
                    estimated_input, output_limit, repair=attempt > 1, allow_partial=True
                )
                usage = usage.model_copy(update={"output_tokens": reserved_output})
                reserved = True
                result = self.llm.complete_json(
                    model,
                    messages,
                    schema,
                    budget.deadline,
                    temperature=0.2,
                    max_tokens=reserved_output,
                    usage_callback=usage_values.append,
                )
                budget.check()
                status = "completed"
            except (ValidationError, json.JSONDecodeError) as exc:
                error = type(exc).__name__ + ":" + str(exc)[:600]
                status = "schema_error"
                if attempt == 2:
                    raise
                messages.append(
                    {
                        "role": "user",
                        "content": "Return valid JSON matching the schema; omit unsupported fields. "
                        + str(exc)[:300],
                    }
                )
            except BaseException as exc:
                error = type(exc).__name__
                status = (
                    "timed_out"
                    if isinstance(exc, (TimeoutError, APITimeoutError))
                    else "cancelled"
                    if budget.cancel.is_set()
                    else "failed"
                )
                raise
            finally:
                self.slots.release()
                if usage_values:
                    usage = usage_values[-1]
                if reserved:
                    budget.settle(estimated_input, reserved_output, usage)
                run_id = self.store.agent_run(
                    job.job_id,
                    role,
                    attempt,
                    model,
                    candidate_version,
                    timestamp,
                    (time.monotonic() - start) * 1000,
                    status,
                    usage.model_dump(),
                    result.model_dump(mode="json") if result else None,
                    error,
                    prompt_version="v2:"
                    + hashlib.sha256(messages[0]["content"].encode()).hexdigest()[:16],
                )
            if status == "completed":
                return result, run_id
        raise RuntimeError("Unreachable role state")


def compact_schema(value):
    if isinstance(value, dict):
        return {
            k: compact_schema(v)
            for k, v in value.items()
            if k not in ("title", "description", "default")
        }
    if isinstance(value, list):
        return [compact_schema(v) for v in value]
    return value


def reachable_schema(schema):
    """Discard unused definitions after a role-specific schema projection."""
    definitions = schema.get("$defs", {})
    needed = set()

    def visit(value):
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if reference.startswith("#/$defs/"):
                name = reference.rsplit("/", 1)[-1]
                if name not in needed:
                    needed.add(name)
                    visit(definitions[name])
            for key, child in value.items():
                if key != "$defs":
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    return {**schema, "$defs": {name: definitions[name] for name in sorted(needed)}}
