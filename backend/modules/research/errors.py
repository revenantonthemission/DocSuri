"""Typed, non-revealing domain refusals at the research boundary."""


class ResearchError(RuntimeError):
    def __init__(self, code: str, *, current: dict | None = None):
        super().__init__(code)
        self.code = code
        self.current = current
