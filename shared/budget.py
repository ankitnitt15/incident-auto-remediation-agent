import threading
import time


class BudgetExceededError(RuntimeError):
    pass


class BudgetTracker:
    """Enforces the triage LLM-call ceiling and reports elapsed time against
    the time-to-first-action target. Thread-safe: subagents call record_call()
    concurrently from a ThreadPoolExecutor.

    5000 alerts/day steady state, 90s p99 time-to-first-action, ~20s/LLM call,
    5 calls running in parallel => 4 rounds x 5 = a 20-call ceiling per triage.
    """

    def __init__(self, max_llm_calls: int = 20, time_budget_seconds: float = 90.0):
        self.max_llm_calls = max_llm_calls
        self.time_budget_seconds = time_budget_seconds
        self._calls_used = 0
        self._lock = threading.Lock()
        self._start = time.monotonic()

    def record_call(self) -> None:
        with self._lock:
            if self._calls_used >= self.max_llm_calls:
                raise BudgetExceededError(
                    f"LLM call budget exhausted ({self.max_llm_calls} calls) for this triage"
                )
            self._calls_used += 1

    @property
    def calls_used(self) -> int:
        with self._lock:
            return self._calls_used

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start

    def within_call_budget(self) -> bool:
        return self.calls_used <= self.max_llm_calls

    def within_time_budget(self) -> bool:
        return self.elapsed_seconds() <= self.time_budget_seconds


if __name__ == "__main__":
    tracker = BudgetTracker(max_llm_calls=2, time_budget_seconds=90.0)
    tracker.record_call()
    tracker.record_call()
    print(f"calls_used={tracker.calls_used} within_budget={tracker.within_call_budget()}")
    try:
        tracker.record_call()
    except BudgetExceededError as e:
        print(f"correctly raised: {e}")
