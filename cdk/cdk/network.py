"""
Generates VPC, subnets and NAT gateway.
SPDX-License-Identifier: Apache 2.0
"""

from constructs import Construct
import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
import aws_cdk.aws_logs as logs
from aws_cdk import (aws_iam as iam )

class Vpc(Construct):
    _vpc = None
    def __init__(self, scope: Construct, id: str,  vpc_cidr, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self._vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=3,
            cidr=vpc_cidr,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT,
                    name="Private",
                    cidr_mask=28,
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name="Public",
                    cidr_mask=28,
                ),
            ],
            nat_gateway_provider=ec2.NatProvider.gateway(),
            nat_gateways=1,  # Default - one NAT gateway/instance per AZ,
            enable_dns_support=True,
            enable_dns_hostnames=True
        )

        log_group = logs.LogGroup(self, "MyCustomLogGroup")
    

        role = iam.Role(self, "Flowlogsrole",
            assumed_by=iam.ServicePrincipal("vpc-flow-logs.amazonaws.com")
        )

        ec2.FlowLog(self, "FlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(self._vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(log_group, role)
        )

    def getVpc(self):
        return self._vpc