"""Step 20 (f): U5's production modules open no logging channel.

U5's security design records failure records as its only audit output: no new logging
channel. The modules are the backend files U5's coverage report measures
(tests/u5_topics_digests/source_scan.py); each is parsed, and none may import a logging
library, build a logger, call `print` or write to a standard stream. The scan is shown
to find each planted case, and not to mistake a name that only contains `print`.
"""

from tests.u5_topics_digests.source_scan import logging_uses, production_modules, relative


def test_u5_production_modules_import_no_logger_and_call_no_print():
    modules = production_modules()
    names = {relative(path) for path in modules}
    assert {
        "backend/modules/topics/delivery.py",
        "backend/modules/topics/scheduler.py",
        "backend/modules/accounts/integrations/digest_email.py",
        "backend/u5_host.py",
        "backend/u5_policy.py",
        "backend/u5_real_delivery.py",
    } <= names
    assert not any(name.startswith("scripts/") for name in names)
    found = {
        relative(path): uses
        for path in modules
        if (uses := logging_uses(path.read_text(), str(path)))
    }
    assert found == {}


def test_the_scan_finds_each_planted_logging_channel():
    planted = (
        "import logging\n"
        "import structlog.stdlib\n"
        "from loguru import logger\n"
        "import sys\n"
        "log = logging.getLogger(__name__)\n"
        "print('digest sent')\n"
        "sys.stderr.write('x')\n"
        "sys.stdout.flush()\n"
    )
    assert sorted(logging_uses(planted)) == sorted(
        [
            "import logging",
            "import structlog.stdlib",
            "from loguru import",
            "getLogger",
            "print()",
            "sys.stderr",
            "sys.stdout",
        ]
    )
    clean = "import json\npreference_fingerprint(x)\nprint_preview = 1\nobject.print\n"
    assert logging_uses(clean) == []
