"""VPC + subnets — inherited from U3 deployment-architecture.md §2.

NAT Gateway excluded ($0); Fargate in public subnets (IGW outbound), data stores in isolated.
2 AZ (ap-northeast-2a, ap-northeast-2c)."""

from aws_cdk import Stack
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from .profile import is_dev


class NetworkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        dev = is_dev(self)

        self.vpc = ec2.Vpc(
            self, "Vpc",
            vpc_name="docsuri-vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            # NAT 배제 — 비용 절감 (U3 확정). dev (serverless-plan Phase 1-②): the maintenance
            # crons run as VPC Lambdas that need AWS API egress (Secrets Manager / CloudWatch /
            # EventBridge) — Lambda ENIs get no public IP, so dev adds ONE NAT gateway + the
            # PrivateEgress group below. Prod stays NAT-free (Fargate egresses via IGW).
            nat_gateways=1 if dev else 0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
                # dev-only, appended LAST so the existing Public/Isolated CIDR allocations
                # (10.0.0-3.0/24) are untouched; this group takes 10.0.4-5.0/24 of the /16.
                *(
                    [
                        ec2.SubnetConfiguration(
                            name="PrivateEgress",
                            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                            cidr_mask=24,
                        )
                    ]
                    if dev
                    else []
                ),
            ],
        )
