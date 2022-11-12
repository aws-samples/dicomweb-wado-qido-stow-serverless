"""
stowrs-to-s3 service entrypoint. Contains the business logic to configure the service per the env variables,
run the web servcie, and process the copy of the DICOM files to S3.

SPDX-License-Identifier: Apache 2.0
"""

import os
from io import BytesIO
from http import HTTPStatus
import string
from flask import Flask, render_template, request
from flask import Response
from multipart_reader import MultipartReader
import xml.etree.ElementTree as ET
from pydicom import dcmread
import werkzeug
from wsproto import Headers
from StowRsXmlResponse import *
from StowRsJsonResponse import *
import logging
import uuid
import collections
from S3FileManager import *
from waitress import serve
import time


app = Flask(__name__)
tempfolder= os.getcwd()+"/out/"
finishedTransactions = collections.deque([])
filesToDelete = collections.deque([])
destinationBucket = None



@app.route("/studies", methods=["POST"])
def callMethod():
    return _StowRsReceiver(None)

@app.route("/studies/<studyInstanceUID>", methods=["POST"])
def callMethodwithStudyUID(studyInstanceUID):
    return _StowRsReceiver( studyInstanceUID )


def _StowRsReceiver( StudyUID ):
    """
    This methods handles the reception of DICOM DATA via STOW-RS protocol.
    It specifically handles the binary mode with no Study Instance provided as part of the URL, allpwing for any instance from any study to be received and stored.

    Args:
        None

    Returns:
        None

    Raises:
        None
    """

    hd = request.headers.to_wsgi_list()
    reader = MultipartReader(hd, request.stream)

    transactionuuid = uuid.uuid4()
    httpstatus = 200

    
    fileinstance =0 
    logging.debug(f"Receiving STOW-RS connection, assigned to Tran ID :{str(transactionuuid)}.")
    try:
        successInstance = []
        failedInstance = []
        while rFile := reader.next():
            try:
                fileinstance = fileinstance+1
                try:
                    #08/04/2022 - Test the exception handling for this use case.
                    storelocation = tempfolder+str(transactionuuid)
                    os.makedirs(storelocation, exist_ok=True)
                    filepath = storelocation+"/file_"+str(fileinstance)
                    with open(filepath, "wb") as binary_file:
                        binary_file.write(rFile.read()) 
                except:
                    ds = adapt_dataset_from_bytes(rFile.read())   
                    failedInstance.append([ds["00080016"].value, ds["00080018"].value, "A700"])
                    httpstatus = 202
                    continue
                try:
                    ds = dcmread(filepath,  specific_tags = { "00080016" , "0020000D" , "0020000E" , "00080018"})
                    if( StudyUID is not None) and ( StudyUID != ds["0020000D"].value):
                        logging.warning(f"Received instance does not belong to study {StudyUID}, rejecting.")
                        failedInstance.append([ds["00080016"].value, ds["00080018"].value, "910"]) # do not add this entry in S3Sender. The error code is made up, the spec does not specify which one to use.
                        filesToDelete.append(filepath)
                        httpstatus = 202
                        continue
                except Exception as ex:
                    logging.error(ex)

                studyinstanceUID = ds["0020000D"].value
                seriesInstanceUID = ds["0020000E"].value
                instanceUID = ds["00080018"].value
                
                filelocation , dicomtree = moveFileInDicomTreeDir(storelocation+"/file_"+str(fileinstance), str(transactionuuid) , studyinstanceUID , seriesInstanceUID , instanceUID ) 
                if(WadoURL is None):
                    wadoUrl = ""
                    retrieveUrl = ""
                else:
                    wadoUrl = f"{WadoURL}/studies/{studyinstanceUID}/series/{seriesInstanceUID}/instances/{instanceUID}"
                    retrieveUrl = f"{WadoURL}/studies/{studyinstanceUID}"
                successInstance.append([ds["00080016"].value, ds["00080018"].value, wadoUrl, None ])
                S3Sender.AddSendJob([filelocation, dicomtree] )

            except Exception as ex:
                logging.error(f"Could not process the instance {fileinstance} :  {ex}")
                failedInstance.append([ds["00080016"].value, ds["00080018"].value, "0110"]) 
                httpstatus = 202
    except StopIteration as serror:
        logging.debug(f"{str(fileinstance)} files received." )
    resp=""

    if(request.headers.get('Accept').lower() != "application/dicom+xml"):
        logging.info("Sending the association response as a JSON document.")
        resp = StowRsJsonResponse.generateResponse(successInstance, failedInstance, retrieveUrl)
        mimetype = 'text/json'
        contentType = 'application/json'  
    else:
        logging.info("Sending the association response as a XML document.")
        resp = StowRsXmlResponse.generateResponse(successInstance, failedInstance, retrieveUrl)
        mimetype= 'text/xml'
        contentType = 'application/xml'
         #some app like 3D slicer sends */* in their request header "Accept", 


    if( len(successInstance) == 0):
        httpstatus = 400

    finishedTransactions.append(str(transactionuuid))
    logging.debug(f"HTTP STATUS : {httpstatus}\r\nMIME-TYPE : {mimetype}\r\nCONTENT-TYPE : {contentType}\r\nPAYLOAD : \r\n{resp}")
    logging.debug(f"{str(transactionuuid)} removed from active connections list. status {httpstatus} will be returned.")
    time.sleep(responsedelay)
    return Response(status = httpstatus  ,response=resp, mimetype=mimetype , content_type=contentType)

def adapt_dataset_from_bytes(blob):
    """
    Attempt to convert a data blob into a bytes array and read the required DICOM tags for the XML response for this specific instance to be constructed.

    Args:
        blob , a data blob which should contains the DICOM object.

    Returns:
        the pydicom dataset object containing the tags "00080016" , "0020000D" , "0020000E" , "00080018"

    Raises:
        None
    """
    # you can just read the dataset from the byte array
    dataset = dcmread(BytesIO(blob), specific_tags = { "00080016" , "0020000D" , "0020000E" , "00080018"})
    return dataset


def moveFileInDicomTreeDir(currentfilename ,transactionuuid , studyUID , seriesUID, instanceUID):
    """
    This methods re-organize the received DICOM files on the filesystem by creating a directory structure and copying all the files of a sames series in different folders.
    The strucuture is shaped like : ./out/transactionuuid/studyuid/seriesuid/sopinstanceuid.dcm
    Args:
        currentfilename :   A string representing the aboslute path to the file location after reception.
        transactionuuid :   The transaction uid generated at the reception of the HTTP request.
        studyUID :          The Study Instance UID of the instance. tag [0020000D] value.
        seriesUID :         The Series Instance UID of the instance. tag [0020000E] value.
        instanceUID :       The SOP Instance UID of the instance. tag [00080018] value.

    Returns:
        newFilePath :       The new absolute file path after the file has been moved.
        dicomFilePath :     A partial path representing the DICOM Tree to the object
                            Eg : /studyuid/seriesuid/sopinstanceuid.dcm
    Raises:
        None
    """    
    newlocation = tempfolder+"/"+transactionuuid+"/"+studyUID+"/"+seriesUID+"/"+instanceUID
    DICOMTreeFolder = "/"+studyUID+"/"+seriesUID+"/"+instanceUID
    newlocation = os.path.join(tempfolder, transactionuuid ,studyUID , seriesUID )
    os.makedirs(newlocation, exist_ok=True)
    os.replace(currentfilename, newlocation+"/"+instanceUID+".dcm")
    newFilePath = newlocation+"/"+instanceUID+".dcm"
    dicomFilePath = DICOMTreeFolder+".dcm"
    return newFilePath , dicomFilePath

def __fileSystemCleaner():
    """
    This methods is use as code logic for a thread. it monitor which files are marked as sent by the S3FileManager and delete them from the filesystem.
    Args:
        None
    Returns:
        None
    Raises:
        None
    """   
    while(True):
        try:
            #Delete files on the filesystem for instance files which should not have been sent within this association.
            if(len(filesToDelete) > 0 ):
                fpath = filesToDelete.popleft()
                logging.debug("Removing instance {obj[0]} from filesystem.")
                os.remove(fpath)

            #Delete files which were successfully sent. 
            obj = S3Sender.GetInstanceSent()
            if obj is not None:
                logging.debug("Removing instance {obj[0]} from filesystem.")
                os.remove(obj[0])
            else:
                sleep(0.1)
        except Exception as err:
            logging.error(str(err))


def setLogLevel():
    """
    This methods is used to set the log level base on the LOGLEVEL env variable if provided.
    If the env variable is not provided, or if the provided value does not match any of the following keywords the method set the log level to INFO.
    Keywords:
        ERROR
        WARNING
        INFO
        DEBUG
        CRITICAL
    Args:
        None
    Returns:
        None
    Raises:
        None
    """   
    try:
        loglevel = os.environ["LOGLEVEL"]
        if loglevel.upper() == "INFO" :
            logging.basicConfig(level=logging.INFO)
            return 
        if loglevel.upper() == "WARNING" :
            logging.basicConfig(level=logging.WARNING)
            return 
        if loglevel.upper() == "ERROR" :
            logging.basicConfig(level=logging.ERROR)
            return 
        if loglevel.upper() == "DEBUG" :
            logging.basicConfig(level=logging.DEBUG)
            return 
        if loglevel.upper() == "CRITICAL" :
            logging.basicConfig(level=logging.CRITICAL)
            return 
        #If none of the values were found to match. We set the log level to INFO.    
        logging.basicConfig(level=logging.INFO)
    except:
        logging.basicConfig(level=logging.INFO)



if __name__ == "__main__":
    setLogLevel()

    try:
        destinationBucket = os.environ['BUCKETNAME']
    except:
        logging.error("No BUCKETNAME env variable provided.")
        exit()
    try:
        EdgeId = os.environ['PREFIX']
    except:
        EdgeId = ""
        logging.info("No PREFIX env variable provided. data will be stored at the root of the bucket.")

    try:
        WadoURL = os.environ['WADOURL']
        if WadoURL[-1] == '/':
            WadoURL = WadoURL.rstrip(WadoURL[-1])
        logging.debug(f"WADOURL = {WadoURL}")
    except:
        WadoURL = None
        logging.warning("No WADOURL env variable provided. the repsonse won't contain RetrieveURL tags.")

    try:
        responsedelaystr = os.environ['RESPONSEDELAY']
        print(responsedelaystr)
        responsedelay = int(responsedelaystr)
        print("Response delay : "+str(responsedelay))
    except:
        responsedelay = 0
        

        
    S3Sender = S3FileManager( EdgeId, destinationBucket)
    
    logging.debug("Starting the file cleaner thread.")
    thread = Thread(target = __fileSystemCleaner)
    thread.start()
    
    logging.info("STOW-RS service started.")
    serve(app, host="0.0.0.0", port=8080, url_scheme='http', max_request_body_size=4294967296)
