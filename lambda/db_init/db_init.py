import logging
import os
import boto3

# https://github.com/aws-cloudformation/custom-resource-helper
from crhelper import CfnResource

helper = CfnResource(log_level="DEBUG")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

for var in ['CLUSTER_ARN', 'SECRET_ARN', 'DB_NAME']:
    if not var in os.environ:
        print(f"ERROR: Environment variable {var} not defined")
        exit(1)

cluster = os.environ['CLUSTER_ARN']
secret = os.environ['SECRET_ARN']
db = os.environ['DB_NAME']

sql_cr = '''
DROP TABLE IF EXISTS study_series;
CREATE TABLE study_series (
  id  SERIAL PRIMARY KEY,
  study_instance_uid    varchar(255) NOT NULL,
  patient_name          varchar(255),
  patient_id            varchar(255),
  study_date            varchar(255),
  study_time            varchar(255),
  accession_number      varchar(255),
  study_id              varchar(255),
  study_description     varchar(255),
  modalities_in_std     varchar(255),
  series_number         varchar(255),
  series_instance_uid   varchar(255) NOT NULL,
  modality              varchar(16),
  series_description    varchar(255)
);

DROP INDEX IF EXISTS std_ser_uid_ind;
CREATE UNIQUE INDEX std_ser_uid_ind ON study_series (study_instance_uid, series_instance_uid);
'''

sql_del = '''
DROP INDEX IF EXISTS std_ser_uid_ind;
DROP TABLE IF EXISTS study_series;
'''


@helper.create
@helper.update
def schema_create(event, _):
    logger.info("Got create/update event with {}".format(event))
    client = boto3.client('rds-data')
    client.execute_statement(database=db, secretArn=secret, resourceArn=cluster, sql=sql_cr)


@helper.delete
def schema_delete(event, _):
    logger.info("Got delete event with {}".format(event))
    client = boto3.client('rds-data')
    client.execute_statement(database=db, secretArn=secret, resourceArn=cluster, sql=sql_del)


def lambda_handler(event, context):
    helper(event, context)
