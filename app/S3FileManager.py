"""
S3FileManager.py : A class to facilitate and tack the copy of files to S3. 

SPDX-License-Identifier: Apache 2.0
"""

import boto3
import botocore
from botocore.config import Config
import os
import collections
from time import sleep
from threading import Thread
import logging


class S3FileManager:

    session = None
    s3 = None
    status = 'idle'
    DICOMInstancetoSend = None
    DICOMInstanceSent = None
    InstanceId= None
    EdgeId = None
    bucket_name = None
    config = Config(s3={"use_accelerate_endpoint": True})
    aws_access_key_id = None
    aws_secret_access_key = None
    threadList = []
    threadCount = 16
 

    def __init__(self, EdgeId, bucketname):
        self.bucket_name = bucketname
        self.EdgeId = EdgeId
        self._configure(EdgeId, bucketname)


    def _configure(self, EdgeId , bucketname):

        self.bucket_name = bucketname
        logging.debug(f"S#FileManager configure for {self.threadCount} threads.")
        logging.debug(f"S3 threads will be copying files to the bucket {bucketname}.")
        poolsize = self.threadCount+5
        try:
            self.threadCount = int(os.environ['THREADCOUNT'])
        except:
            logging.debug(f"No THREADCOUNT env variable, defaulting to {self.threadCount}.")
        try:
            if self.aws_access_key_id == None:
                self.aws_access_key_id = os.environ['AWS_ACCESS_KEY']
            if self.aws_secret_access_key == None:   
                self.aws_secret_access_key = os.environ['AWS_SECRET_KEY']
            self.session = boto3.Session(self.aws_access_key_id,self.aws_secret_access_key)
            
            self.s3 = self.session.resource('s3' , config=botocore.client.Config(max_pool_connections=poolsize))

        except:          # we might be in greengrass mode :
            logging.debug("No AWS IAM credentials provided defaulting to greengrass authentication provider")    
            try:
                self.session = boto3.Session()
                self.s3 = self.session.resource('s3' ,config=botocore.client.Config(max_pool_connections=poolsize))
                    
            except:
                logging.error("There was an issue creating an boto3 session.")   

  

        
        self.DICOMInstancetoSend = collections.deque([])
        self.DICOMInstanceSent = collections.deque([])
        self.EdgeId = EdgeId

        self.PrepareS3Threads()

    def __uploadfile(self, obj):
        #08/04/2022 - Add support for multipart upload.
        self.status = 'uploading'
        logging.debug(f"Bufferred Files in queue to send to {self.bucket_name} : {len(self.DICOMInstancetoSend)}")
        try:
            self.s3.Bucket(self.bucket_name).upload_file(obj[0],self.EdgeId+obj[1])
        except Exception as ex:
            logging.error(f"Could not copy the file to S3: {ex}")
        self.status = 'idle'
   
    def AddSendJob(self,DCMObj):
            self.DICOMInstancetoSend.append(DCMObj)  # DCMObj should contains the absolutfile location , and its relative s3 path
            

    def __s3upload(self,args):
        while(True):
            if len(self.DICOMInstancetoSend) > 0:
                obj = self.DICOMInstancetoSend.popleft()
                self.__uploadfile(obj)
                self.DICOMInstanceSent.append(obj)
            else:
                sleep(0.1)
    

    def GetInstanceSent(self):
        if len(self.DICOMInstanceSent) > 0:
            obj = self.DICOMInstanceSent.popleft()
            return obj
        else:
            return None

    def PrepareS3Threads(self):
        for x in range(self.threadCount):
            logging.debug("[ServiceInit] - S3 thread # "+str(x))
            thread = Thread(target = self.__s3upload, args = ( 1, ))
            thread.start()
            self.threadList.append(thread)
