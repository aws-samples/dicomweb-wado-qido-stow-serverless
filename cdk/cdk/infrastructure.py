from typing import Any

from constructs import Construct
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_notifications as s3_notifications,
)

from .function import PythonLambda
from .storage import S3Bucket
from .api import ApiGwLambda
from .static_content import StaticContentDeployment
from .cdn import CloudFront
from .network import Vpc
from .db import DynamoDb, AuroraServerless
from .custom import CustomLambdaResource
from .storage import S3Bucket
from .network import Vpc
from .fargate import FargateService
from .nlb import StowNLB
from .cfPrefixListSelector import cfPrefixListSelector


from .roles import Roles



import time


class StaticDicomWeb(Stack):
    def __init__(self, scope: Construct, id: str, vpc_cidr, db_name, lambda_config, cdn_config, certificate_config ,task_definition , allowed_peers ,**kwargs):
        super().__init__(scope, id, **kwargs)

        region = self.region
        account = self.account

        # Lambda function for processing DICOM files from S3 event notification
        fn_dicom_to_static_web = PythonLambda(self, "DicomToStaticWeb", lambda_config["DicomToStaticWeb"])

        # S3 bucket for incoming DICOM files
        s3_landing = S3Bucket(self, "LandingBucket")

        # S3 bucket notification to call Lambda to process DICOM files
        s3_landing.bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3_notifications.LambdaDestination(fn_dicom_to_static_web.fn),
        )
        s3_landing.bucket.grant_read(fn_dicom_to_static_web.fn)

        # S3 static content bucket
        s3_static_web = S3Bucket(self, "StaticWebBucket")
        s3_static_web.bucket.grant_read_write(fn_dicom_to_static_web.fn)

        # S3 OHIF viewer bucket
        s3_ohif_viewer = S3Bucket(self, "OhifViewerBucket")

        # QIDO Lambda
        fn_qido = PythonLambda(self, "QidoQuery", lambda_config["QidoQuery"])

        # REST API for QIDO calls
        rest_api = ApiGwLambda(self, "QidoApi", fn_qido.fn)
        api_url = rest_api.apigw.rest_api_id + ".execute-api." + region + ".amazonaws.com"

        # Deploy viewer to S3
        ohif_viewer_deployment = StaticContentDeployment(
            self, "OhifViewer", "../viewer", s3_ohif_viewer.bucket, prune=True
        )

        #VPC and subnets creation.
        vpc = Vpc(self, "Network", vpc_cidr)

        # Aurora Postgres serverless for study/series level information
        aurora = AuroraServerless(self, "StudySeries", vpc._vpc, db_name)

        #Load balancer for Fargate Task creation.
        lb = StowNLB(self, "nlb", vpc.getVpc(), certificate_config,  s3_static_web.bucket) 

        # CloudFront distribution for 1/ viewer, 2/ dicomweb output and 3/ qido queries
        cf = CloudFront(self, "StaticDicomWebDistribution", s3_ohif_viewer.bucket, s3_static_web.bucket, api_url, certificate_config["stow_fqdn"], cdn_config)

        # DynamoDb for study-level information
        ddb_st = DynamoDb(self, "StudyDdb", "std_uid", "pat_name")
        ddb_st.db.grant_write_data(fn_dicom_to_static_web.fn)
        ddb_st.db.grant_read_write_data(fn_qido.fn)

        # DynamoDb for Series-level information
        ddb_ser = DynamoDb(self, "SeriesDdb", "ser_uid", "ser_number")
        ddb_ser.db.grant_write_data(fn_dicom_to_static_web.fn)
        ddb_ser.db.grant_read_write_data(fn_qido.fn)



        # Lambda function for creating Postgres schema
        fn_db_init = PythonLambda(self, "DbInit", lambda_config["DbInit"])

        # Custom resource to add Postgres schema
        postgres_schema = CustomLambdaResource(self, "PostgresSchema", fn_db_init.fn)

        # Run custom resource to add Postgres schema after Aurora Postgres is complete
        postgres_schema.cr.node.add_dependency(aurora)

        # Custom resource to update viewer settings
        fn_update_viewer_config = PythonLambda(self, "ViewerConfigUpdate", lambda_config["ViewerConfigUpdate"])
        viewer_config = CustomLambdaResource(
            self,
            "ViewerConfig",
            fn_update_viewer_config.fn,
            cr_properties={"RunEveryTimeCdkIsDeployed": str(time.time())},
        )
        viewer_config.cr.node.add_dependency(ohif_viewer_deployment)
        viewer_config.cr.node.add_dependency(cf)
        # Update viewer settings permission - s3 to update config, CloudFront to invalidate file
        s3_ohif_viewer.bucket.grant_read_write(fn_update_viewer_config.fn)
        fn_update_viewer_config.fn.role.attach_inline_policy(
            iam.Policy(
                self,
                "AllowCFInvalidation",
                statements=[
                    iam.PolicyStatement(
                        actions=["cloudfront:*Invalidation"],
                        resources=[
                            "arn:aws:cloudfront::" + account + ":distribution/"+cf.distribution.distribution_id
                        ],
                    )
                ],
            )
        )

        # Allow Lambdas to access Aurora Postgres
        aurora.db.grant_data_api_access(fn_dicom_to_static_web.fn)
        aurora.db.grant_data_api_access(fn_qido.fn)
        aurora.db.grant_data_api_access(fn_db_init.fn)

        # Add Lambda environment variables
        fn_dicom_to_static_web.fn.add_environment("VAR_DEBUG", "1")
        fn_dicom_to_static_web.fn.add_environment("VAR_OUTPUT_BUCKET", s3_static_web.bucket.bucket_name)
        fn_dicom_to_static_web.fn.add_environment("VAR_REGION", region)
        fn_dicom_to_static_web.fn.add_environment("MULTIPART_BOUNDARY_MARKER", "boundary_marker")
        fn_dicom_to_static_web.fn.add_environment("VAR_STATIC_DICOM_PREFIX", "dicomweb/")
        fn_dicom_to_static_web.fn.add_environment("URI_PREFIX", cf.distribution.domain_name)
        fn_dicom_to_static_web.fn.add_environment("VAR_DYNAMO_TABLE", ddb_st.db.table_name)
        fn_dicom_to_static_web.fn.add_environment("VAR_DYNAMO_TABLE_SER", ddb_ser.db.table_name)
        fn_dicom_to_static_web.fn.add_environment("CLUSTER_ARN", aurora.db.cluster_arn)
        fn_dicom_to_static_web.fn.add_environment("SECRET_ARN", aurora.db.secret.secret_arn)
        fn_dicom_to_static_web.fn.add_environment("DB_NAME", db_name)

        fn_qido.fn.add_environment("VAR_DEBUG", "1")
        fn_qido.fn.add_environment("VAR_DYNAMO_TABLE", ddb_st.db.table_name)
        fn_qido.fn.add_environment("VAR_DYNAMO_TABLE_SER", ddb_ser.db.table_name)
        fn_qido.fn.add_environment("CLUSTER_ARN", aurora.db.cluster_arn)
        fn_qido.fn.add_environment("SECRET_ARN", aurora.db.secret.secret_arn)
        fn_qido.fn.add_environment("DB_NAME", db_name)

        fn_db_init.fn.add_environment("CLUSTER_ARN", aurora.db.cluster_arn)
        fn_db_init.fn.add_environment("SECRET_ARN", aurora.db.secret.secret_arn)
        fn_db_init.fn.add_environment("DB_NAME", db_name)

        qido_root_apigateway = "https://" + api_url + "/prod"
        qido_root = "https://" + cf.distribution.domain_name + "/qido"
        wado_root = "https://" + cf.distribution.domain_name + "/dicomweb"

        fn_update_viewer_config.fn.add_environment("CF_DISTRIBUTION_ID", cf.distribution.distribution_id)
        fn_update_viewer_config.fn.add_environment("QIDO_ROOT", qido_root)
        fn_update_viewer_config.fn.add_environment("WADO_ROOT", wado_root)
        fn_update_viewer_config.fn.add_environment("OHIF_VIEWER_BUCKET", s3_ohif_viewer.bucket.bucket_name)


        cloudFrontPrefixLister = cfPrefixListSelector(self, "prefixSelector", region)
        #If the value is anything else than ACM, we default to S3 mode.
        if(certificate_config["certificate_mode"].upper() != "ACM"):
            #S3 bucket to store certificates.
            S3bucket_certs = S3Bucket(self, certificate_config["certificate_bucket"])
            taskRole = Roles(self, "TaskRole", s3_landing.bucket.bucket_arn , s3_landing.bucket.bucket_arn )
            

            if(certificate_config["certificate_auth_mode"].upper() == 'CLIENTAUTH'):
                authmode = 'clientauth'
            else:
                authmode = 'anonymous'
            fg=FargateService(self, "Fargate", vpc=vpc.getVpc(), task_role=taskRole.getRole() , task_definition=task_definition , dicom_bucket_name=s3_landing.bucket.bucket_name , certificate_bucket_name=S3bucket_certs.bucket.bucket_name ,  loadbalancer=lb , authentication_mode=authmode, certificate_mode="FROMS3" , wado_root=wado_root , cf_prefixlist_id=cloudFrontPrefixLister.prefixListId )
        else:
            #we do not need to create the certificate bucket in this mode, neither we need to add privilegs for it to the role.
            taskRole = Roles(self, "TaskRole", dicom_s3_arn=s3_landing.bucket.bucket_arn  , cert_s3_arn=None )
            fg=FargateService(self, "Fargate", vpc=vpc.getVpc(), task_role=taskRole.getRole() , task_definition=task_definition , dicom_bucket_name=s3_landing.bucket.bucket_name, certificate_bucket_name=None , loadbalancer=lb , authentication_mode="anonymous" , certificate_mode="ACM" , wado_root=wado_root, cf_prefixlist_id=cloudFrontPrefixLister.prefixListId )
            

        CfnOutput(self, "qidoRoot", value=qido_root, description="QIDO-RS Root")
        CfnOutput(self, "wadoRoot", value=wado_root, description="WADO-RS Root")
        CfnOutput(self, "qidoRootApiGateway", value=qido_root_apigateway, description="QIDO-RS Root via API Gateway")
        CfnOutput(self, "cloudfrontDistributionId", value=cf.distribution.distribution_id, description="CloudFront Dsitribution Id")
        CfnOutput(self, "STOWRSNetworkLoadBalancerDNS", value=lb._lb.load_balancer_dns_name, description="DNS name of the STOW-RS network load balancer")

