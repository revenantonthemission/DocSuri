"""Safe event projection; never logs raw exception bodies, SQL, paths or credentials."""

import logging

from ..contracts.models import SafeObservation


class ObservationAdapter:
    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger("docsuri.platform_integrity")

    def emit(self, observation: SafeObservation) -> None:
        self._logger.log(
            {"info": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR}[
                observation.level
            ],
            observation.model_dump_json(),
        )
