"""
Fetches certificates files from S3 and configure nginx for anonymous or ClientAuth mode.
This script is invoked during the container start-up before the nginx service is being started.
SPDX-License-Identifier: Apache 2.0
"""

import os
import boto3
import logging

"""
This method configue the container to execute Certbot if no valid certs are found on the S3 Bucket. It also exports the certs on S3 when issued.
Args:
    None
Returns:
    None
Raises:
    None
"""   
def _ConfigureCertFromS3():
    #Try to read the certs from the S3 bucker and domain_name prefix:
    bucket_name = os.environ["CERT_BUCKETNAME"]
    s3client = _buildS3Client()
    try:
        s3client.Bucket(bucket_name).download_file("certificate.key", "./certificate.key")
        s3client.Bucket(bucket_name).download_file("certificate.crt", "./certificate.crt")
    except Exception as s3error:
        logging.error("The certificate.crt and certificate.key files could not be found at the root of the bucket f{bucket_name}.")
        logging.error(str(s3error))
    


def _setAuthmode():
    try:
        auth_mode=os.environ["AUTH_MODE"]
    except:    
        auth_mode = "anonymous"
    logging.info(f"Setting auth mode to {auth_mode}")
    if(auth_mode.lower() == "clientauth"):
        bucket_name = os.environ["CERT_BUCKETNAME"]
        s3client = _buildS3Client()
        try:
            s3client.Bucket(bucket_name).download_file("truststore.crt", "./truststore.crt")
        except Exception as s3error:
            logging.error("The file truststore.crt could not be found at the root of the bucket f{bucket_name}.")
            logging.error(str(s3error)) 
            return           
        confFile = open("/etc/nginx/nginx.conf")
        confString = confFile.read()
        confFile.close()
        confString=confString.replace("#ssl_verify_client on","ssl_verify_client on")
        confString=confString.replace("#ssl_client_certificate","ssl_client_certificate")

        confFile = open("/etc/nginx/nginx.conf", "w")
        confFile.write(confString)
        confFile.close()
        
        logging.error(confString)


def _buildS3Client():
    try:
        if aws_access_key_id == None:
            aws_access_key_id = os.environ['AWS_ACCESS_KEY']
        if aws_secret_access_key == None:   
            aws_secret_access_key = os.environ['AWS_SECRET_KEY']
        session = boto3.Session(aws_access_key_id,aws_secret_access_key)
        
        s3 = session.resource('s3' )
    except:          # we might be in greengrass mode :
        logging.debug("No AWS IAM credentials provided defaulting to greengrass authentication provider")    
        try:
            session = boto3.Session()
            s3 = session.resource('s3')
                
        except:
            logging.error("There was an issue creating an boto3 session.")  
    
    return s3


try:
    logging.basicConfig(level=logging.INFO)
    certmode = os.environ["CERT_MODE"]
except:
    logging.error("Env variable CERT_MODE was not specified.")
if certmode.upper() == "FROMS3" :
    _ConfigureCertFromS3()
    _setAuthmode()