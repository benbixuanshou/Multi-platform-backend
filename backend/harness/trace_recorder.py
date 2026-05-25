"""TraceRecorder — working memory + decision audit (Harness Module 4 + 6)."""


class TraceRecorder:
    @staticmethod
    def record_step(trace: list, step: str, detail: dict):
        trace.append({"step": step, **detail})

    @staticmethod
    def new_trace() -> list:
        return []
