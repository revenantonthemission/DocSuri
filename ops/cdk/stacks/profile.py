"""Deployment sizing profile.

``-c profile=dev`` selects the trimmed single-AZ dev sizing (personal-account
environment, 2026-08-04). The default keeps the team-production HA values, so a
deploy without the context flag can never silently downsize production.
"""

from aws_cdk import Token
from aws_cdk import aws_rds as rds
from constructs import Construct


def is_dev(scope: Construct) -> bool:
    return scope.node.try_get_context("profile") == "dev"


def db_endpoint(db: rds.IDatabaseInstance | rds.IDatabaseCluster) -> rds.Endpoint:
    """The control-plane DB endpoint regardless of shape.

    dev runs an Aurora Serverless v2 ``DatabaseCluster`` (scale-to-zero) while prod keeps the
    ``DatabaseInstance`` — consumers read ``.hostname`` / ``db_port_as_string`` off this and
    stay agnostic to which one was built.
    """
    return getattr(db, "cluster_endpoint", None) or db.instance_endpoint


def db_port_as_string(db: rds.IDatabaseInstance | rds.IDatabaseCluster) -> str:
    """CFN string token for the DB port.

    ``Endpoint.port`` is a number token in the Python binding (the TS ``portAsString()``
    convenience isn't surfaced); ``Token.as_string`` resolves to the identical
    ``Fn::GetAtt … Endpoint.Port`` JSON as the raw string attribute.
    """
    return Token.as_string(db_endpoint(db).port)
