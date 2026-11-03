"""One deadline and reservation ledger per job, shared by parallel role calls."""

import threading
import time


class BudgetExceeded(RuntimeError):
    pass


class JobCancelled(RuntimeError):
    pass


class Budget:
    def __init__(self, limits, timeout, cancel, clock=time.monotonic):
        self.limits, self.cancel, self.clock = limits, cancel, clock
        self.deadline = clock() + timeout
        self.lock = threading.Lock()
        self.calls = self.output = self.total = 0
        self.repairs = 0

    def check(self):
        if self.cancel.is_set():
            raise JobCancelled("Job cancelled")
        if self.clock() >= self.deadline:
            raise TimeoutError("Cognitive job deadline exceeded")

    def reserve(self, input_tokens, output_tokens, repair=False):
        with self.lock:
            self.check()
            if self.deadline - self.clock() < 0.1:
                raise TimeoutError("Insufficient remaining dispatch time")
            if repair and self.repairs:
                raise BudgetExceeded("Shared schema repair already consumed")
            if (
                self.calls + 1 > self.limits.max_calls
                or self.output + output_tokens > self.limits.output_tokens
                or self.total + input_tokens + output_tokens > self.limits.total_tokens
            ):
                raise BudgetExceeded("Call/token reservation exceeds job budget")
            self.calls += 1
            self.repairs += int(repair)
            self.output += output_tokens
            self.total += input_tokens + output_tokens

    def settle(self, reserved_input, reserved_output, usage):
        with self.lock:
            if usage.source == "provider":
                actual_input = (
                    usage.input_tokens if usage.input_tokens is not None else reserved_input
                )
                actual_output = (
                    usage.output_tokens if usage.output_tokens is not None else reserved_output
                )
                self.output += actual_output - reserved_output
                self.total += actual_input + actual_output - reserved_input - reserved_output

    def report(self):
        with self.lock:
            return {
                "calls": self.calls,
                "accounted_output_tokens": self.output,
                "accounted_total_tokens": self.total,
                "schema_repairs": self.repairs,
            }
