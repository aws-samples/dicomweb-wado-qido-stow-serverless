"""
Config file for the soluiton deployment via CDK
SPDX-License-Identifier: MIT-0
"""


CDK_APP_NAME = "wado-stow-1"

VPC_CIDR = "10.10.0.0/22"


CERTIFICATE = {
    "certificate_arn" : "[replace with an ACM certificate ARN]", #Replace
    "stow_fqdn" : "[replace with your fully qualified domain name]", #Replace
    "certificate_auth_mode" : "anonymous", #Leave as default.
    "certificate_mode" : "ACM", #Leave as default.
    "certificate_bucket" : "", #Leave as default.
}


RESOURCE_TAGS = {
    "tag_list" : {
        "exampletag1" : "examplevalue1",
        "exampletag2" : "examplevalue2"
    }
}


## Advanced configurations - NO changes required for default deployment.

DB_NAME = "study_series"

LAMBDA_CONFIG = {
    "DicomToStaticWeb": {
        "entry": "../lambda/dicom_to_static_web",
        "handler": "lambda_handler",
        "index": "dicom_to_static_web.py",
        "timeout": 15,
        "memory": 1024,
        "layers": ["PyDicom"],
        "reserved_concurrency":1,
    },
    "QidoQuery": {
        "entry": "../lambda/qido_query",
        "handler": "lambda_handler",
        "index": "qido_query.py",
        "timeout": 15,
        "memory": 256,
        "layers": [],
        "reserved_concurrency":0,
    },
    "DbInit": {
        "entry": "../lambda/db_init",
        "handler": "lambda_handler",
        "index": "db_init.py",
        "timeout": 15,
        "memory": 256,
        "layers": [],
        "reserved_concurrency":0,
    },
    "ViewerConfigUpdate": {
        "entry": "../lambda/viewer_config_update",
        "handler": "lambda_handler",
        "index": "viewer_config_update.py",
        "timeout": 15,
        "memory": 256,
        "layers": [],
        "reserved_concurrency":0,
    }
}

CDN_CONFIG = {
    "min_ttl": 0,
    "max_ttl": 120,
    "default_ttl": 60,
}

ALLOWED_PEERS = {
    "peer_list" : {}
}

FARGATE_TASK_DEF = {
    "memory" : 6144,
    "cpu" : 1024,
    "task_count" : 1,               #This defines the number of instances to run behind the load balancer.
    "nginx_container" : {
        "source_directory" : "../nginx",
        "memory" : 2048,
        "cpu" : 1024
    },
    "app_container" : {
        "source_directory" : "../app",
        "memory" : 4096,
        "cpu" : 1024,
        "envs" :{
            "PREFIX" : "STOWFG-1",
            "LOGLEVEL" : "WARNING",
            "RESPONSEDELAY" : "0"
        }
    }
}

