"""
Generates VPC, subnets and NAT gateway.
SPDX-License-Identifier: Apache 2.0
"""

from constructs import Construct
import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
import aws_cdk.aws_logs as logs
from aws_cdk import (aws_iam as iam )


prefixesList = {
    "ap-south-1" : "pl-9aa247f3",
    "eu-north-1" : "pl-fab65393",
    "eu-west-3" : "pl-75b1541c",
    "eu-west-2" : "pl-93a247fa",
    "eu-west-1" : "pl-4fa04526",
    "ap-northeast-3" : "pl-31a14458",
    "ap-northeast-2" : "pl-22a6434b",
    "ap-northeast-1" : "pl-58a04531",
    "ca-central-1" : "pl-38a64351",
    "sa-east-1" : "pl-5da64334",
    "ap-southeast-1" : "pl-31a34658",
    "ap-southeast-2" : "pl-b8a742d1",
    "eu-central-1" : "pl-a3a144ca",
    "us-east-1" : "pl-3b927c52",
    "us-east-2" : "pl-b6a144df",
    "us-west-1" : "pl-4ea04527",
    "us-west-2" : "pl-82a045eb",
}

class cfPrefixListSelector(Construct):
    prefixListId = None

    def __init__(self, scope: Construct, id: str, region: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        self.prefixListId = prefixesList[region]
        print(f"selected Prefix : {self.prefixListId}")