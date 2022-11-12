import boto3
import botocore

import logging
import os
import re

# https://github.com/aws-cloudformation/custom-resource-helper
from crhelper import CfnResource

helper = CfnResource(log_level="INFO")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Collect required environment variables
for var in ["QIDO_ROOT", "WADO_ROOT", "OHIF_VIEWER_BUCKET"]:
    if not var in os.environ:
        print(f"ERROR: Environment variable {var} not defined")
        exit(1)

qido_root = os.environ["QIDO_ROOT"]
wado_root = os.environ["WADO_ROOT"]
ohif_viewer_bucket = os.environ["OHIF_VIEWER_BUCKET"]
distribution_id = os.environ["CF_DISTRIBUTION_ID"]

config_object = "app-config.js"
config_file_path = "/tmp/app-config.js"


# In-place find replace in file
def find_replace(file, pattern, repl):
    with open(file, "r+") as f:
        text = f.read()
        text = re.sub(pattern, repl, text)
        f.seek(0)
        f.write(text)
        f.truncate()


@helper.create
@helper.update
def update_ohif_config(event, _):
    logger.info("Got create/update event with {}".format(event))

    # Download app config from S3
    s3_client = boto3.client("s3")
    s3_client.download_file(ohif_viewer_bucket, config_object, config_file_path)

    # Replace placeholder with data from environment variables
    find_replace(config_file_path, "wadoUriRoot: .*", "wadoUriRoot: '" + wado_root + "',")
    find_replace(config_file_path, "wadoRoot: .*", "wadoRoot: '" + wado_root + "',")
    find_replace(config_file_path, "qidoRoot: .*", "qidoRoot: '" + qido_root + "',")

    # Upload updated app config to S3
    try:
        response = s3_client.upload_file(config_file_path, ohif_viewer_bucket, config_object)
    except botocore.exceptions.ClientError as e:
        logger.error("Error uploading config to S3", e)

    # Invalidate file in CloudFront
    cf_client = boto3.client("cloudfront")
    cf_client.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "Paths": {
                "Quantity": 1,
                "Items": [
                    "/" + config_object,
                ],
            },
            "CallerReference": "ViewerConfig",
        },
    )


@helper.delete
def no_op(_, __):
    logger.info("Got delete, doing nothing. ")
    pass


def lambda_handler(event, context):
    helper(event, context)
