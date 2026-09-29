import os

from hypothesis import settings

settings.register_profile("pr", max_examples=200, derandomize=True, print_blob=True)
settings.register_profile("release", max_examples=2000, derandomize=True, print_blob=True)
settings.load_profile(os.environ.get("R1_TEST_PROFILE", "pr"))
settings.register_profile(
    "stateful",
    max_examples=200 if os.environ.get("R1_TEST_PROFILE") == "release" else 50,
    stateful_step_count=100 if os.environ.get("R1_TEST_PROFILE") == "release" else 50,
    derandomize=True,
    print_blob=True,
)
