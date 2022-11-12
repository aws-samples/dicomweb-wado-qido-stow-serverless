from constructs import Construct

from aws_cdk import aws_s3_deployment as s3_deploy


class StaticContentDeployment(Construct):
    def __init__(self, scope: Construct, id: str, path, bucket, key_prefix="", prune=False, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.deployment = s3_deploy.BucketDeployment(
            self,
            "StaticContentDeployment",
            sources=[s3_deploy.Source.asset(path)],
            destination_bucket=bucket,
            destination_key_prefix=key_prefix,
            prune=prune,
        )
