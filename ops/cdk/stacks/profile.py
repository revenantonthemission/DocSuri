"""Deployment sizing profile.

``-c profile=dev`` selects the trimmed single-AZ dev sizing (personal-account
environment, 2026-08-04). The default keeps the team-production HA values, so a
deploy without the context flag can never silently downsize production.
"""

from constructs import Construct


def is_dev(scope: Construct) -> bool:
    return scope.node.try_get_context("profile") == "dev"
