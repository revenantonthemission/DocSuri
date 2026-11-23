"""The operator tool's commands (U8 plan Steps 29, 31 and 33; the person's decisions of
2026-10-25, "Move U8's code out of U7" and "Its own package's name").

`python -I -m docsuri_ops.u8_platform <command> <word> …`, where the command is one of
`recovery`, `cutover`, `migration`, `inventory` or, by the person's decision of
2026-10-25 ("Add an in-person stop command"), `service` (`service stop|start <label>`,
`service_words`), or, by U8 plan Step 72(b) (NFR9.13), `availability` (`availability
report`, `availability_words`). Every word and flag is the one each
command's own module defines (`--production`, `--environment-file`, the `prog` labels).
In production it runs as `/Library/DocSuri/release/.venv/bin/python -I -m
docsuri_ops.u8_platform …`, and in the composed realm as `backend/.venv/bin/python -m
docsuri_ops.u8_platform … --environment-file /tmp/docsuri-u8-run/environment.json`.
Anything else gets a usage line and exit code 2. U7's envelope, U7's package run as a
module, is as built and refuses these commands.
"""

from __future__ import annotations

import sys

COMMANDS = ("recovery", "cutover", "migration", "inventory", "service", "availability")
USAGE = ("usage: python -I -m docsuri_ops.u8_platform "
         "{recovery,cutover,migration,inventory,service,availability} <word> ...\n")


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else list(argv)
    command = arguments[0] if arguments else None
    if command == "recovery":
        from .recovery_words import main as recovery_main

        return recovery_main(arguments[1:])
    if command == "cutover":
        from docsuri_ops.cutover.tool import main as cutover_main

        return cutover_main(arguments[1:])
    if command in ("migration", "inventory"):
        from docsuri_ops.migration.words import main as words_main

        return words_main(command, arguments[1:])
    if command == "service":
        from .service_words import main as service_main

        return service_main(arguments[1:])
    if command == "availability":
        from .availability_words import main as availability_main

        return availability_main(arguments[1:])
    sys.stderr.write(USAGE)
    return 2
