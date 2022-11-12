from constructs import Construct

from aws_cdk import (
    Duration,
    RemovalPolicy,
    aws_rds as rds,
    aws_dynamodb as dynamodb,
)


class DynamoDb(Construct):
    def __init__(
        self, scope: Construct, id: str, partition_key, sort_key, **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.db = dynamodb.Table(
            self,
            "Ddb",
            partition_key=dynamodb.Attribute(
                name=partition_key, type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name=sort_key, type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )


class AuroraServerless(Construct):
    def __init__(self, scope: Construct, id: str, vpc, db_name, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.db = rds.ServerlessCluster(
            self,
            "AuroraServerless",
            engine=rds.DatabaseClusterEngine.AURORA_POSTGRESQL,
            vpc=vpc,
            enable_data_api=True,
            default_database_name=db_name,
            removal_policy=RemovalPolicy.DESTROY,
            parameter_group=rds.ParameterGroup.from_parameter_group_name(
                self, "ParameterGroup", "default.aurora-postgresql10"
            ),
            scaling=rds.ServerlessScalingOptions(
                auto_pause=Duration.minutes(10),
                min_capacity=rds.AuroraCapacityUnit.ACU_2,
                max_capacity=rds.AuroraCapacityUnit.ACU_32,
            ),
        )
