"""
Generate required roles for Task runtime.
SPDX-License-Identifier: Apache 2.0
"""

from constructs import Construct
from aws_cdk import (aws_iam as iam )

class Roles(Construct):


    _TaskRole = None

    def __init__(self, scope: Construct, id: str, dicom_s3_arn : str, cert_s3_arn : str , **kwargs) -> None :
        super().__init__(scope, id, **kwargs)  

        self._TaskRole = iam.Role(self, "Role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="This Role is used by the Stowrs-to-s3 task to access to S3."
        )
        dicom_TaskRoleStatement = iam.PolicyStatement(
        effect = iam.Effect.ALLOW,
                    actions = [
                        's3:ListBucket',
                        's3:PutObject'
                    ],
                    resources = [dicom_s3_arn  , f"{dicom_s3_arn}/*" ]
                    )
        self._TaskRole.add_to_policy(dicom_TaskRoleStatement)

        if(cert_s3_arn is not None):

            cert_TaskRoleStatement = iam.PolicyStatement(
            effect = iam.Effect.ALLOW,
                        actions = [
                            's3:ListBucket',
                            's3:GetObject',
                            's3:PutObject'
                        ],
                        resources = [cert_s3_arn , f"{cert_s3_arn}/*" ]
                        )               
            self._TaskRole.add_to_policy(cert_TaskRoleStatement)


    def getRoleArn(self):
        return self._TaskRole.role_arn
    
    def getRole(self):
        return self._TaskRole

