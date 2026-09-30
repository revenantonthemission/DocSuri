#!/usr/bin/env python3
"""Debug launchd plist creation and bootstrap."""

from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

REALM_ROOT = Path("/Library/Application Support/DocSuri/rem-2")
WORKER_UIDS = {
    "translate": 700,
    "summarize": 701,
    "novelty": 702,
    "evidence": 703,
}
GROUP = "_docsuri_rem2_worker"
GROUP_NAME = "_docsuri_rem2_worker"
LABEL_PREFIX = "rem-2-content"


def create_plist(label: str, worker_type: str, uid: int, gid: int, working_dir: Path) -> bytes:
    result = {
        "Label": f"org.docsuri.{label}",
        "UserName": f"_docsuri_rem2_{worker_type}",
        "GroupName": "_docsuri_rem2_worker",
        "InitGroups": False,
        "Umask": 0o077,
        "WorkingDirectory": str(working_dir),
        "ProcessType": "Background",
        "ThrottleInterval": 5,
        "ExitTimeOut": 30,
        "RunAtLoad": False,
        "StandardOutPath": str(Path("/Library/Application Support/DocSuri/rem-2/workers/translate") / "logs" / "translate.out"),
        "StandardErrorPath": str(Path("/Library/Application Support/DocSuri/rem-2/workers/translate") / "logs" / "translate.err"),
        "SoftResourceLimits": {"NumberOfFiles": 256, "Core": 0},
        "HardResourceLimits": {"NumberOfFiles": 256, "Core": 0},
    }
    import plistlib
    return plistlib.dumps({"Label": "test", "ProgramArguments": ["/bin/echo", "hello"]}, sort_keys=True)


def test_plist():
    import plistlib
    # Test minimal plist
    test_plist = {
        "Label": "test.label",
        "ProgramArguments": ["/bin/echo", "hello"],
        "RunAtLoad": False,
    }
    data = plistlib.dumps(test_plist, sort_keys=True)
    print("Test plist:")
    print(plistlib.loads(data))
    
    # Write to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".plist", delete=False) as f:
        f.write(plistlib.dumps({
            "Label": "test.bootstrap",
            "ProgramArguments": ["/bin/echo", "hello"],
            "RunAtLoad": False,
        }, sort_keys=True))
        temp_path = f.name
    
    print(f"Temp plist: {temp_path}")
    
    # Try bootstrap
    result = subprocess.run(
        ["launchctl", "bootstrap", "system", temp_path],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"Return code: {result.returncode}")
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")


if __name__ == "__main__":
    import subprocess
    import tempfile
    test_plist()
