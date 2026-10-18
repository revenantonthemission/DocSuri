"""Typed, non-revealing domain refusals at the topics boundary."""


class TopicsError(RuntimeError):
    def __init__(self, code: str, *, current: dict | None = None):
        super().__init__(code)
        self.code = code
        self.current = current
