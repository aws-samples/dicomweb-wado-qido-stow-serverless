"""
StowRsJsonResponse.py : a class used to build a DICOM PS18 STOW-RS response enveloppe in JSON.

SPDX-License-Identifier: Apache 2.0
"""

import pydicom
from pydicom import Dataset , DataElement , Sequence

class StowRsJsonResponse(object):
    
    @staticmethod
    def generateResponse( successlist , failedlist , retrieveUrl):
        RetrievelUrlElement = DataElement("00081190" ,"UR" , retrieveUrl)
        FailedSequence = DataElement("00081198" ,"SQ" , "")
        FailedSequence = StowRsJsonResponse.__buildJsonFailedlist( failedlist , FailedSequence)
        SuccessSequence = DataElement("00081199" ,"SQ", "")
        SuccessSequence = StowRsJsonResponse.__buildJsonSuccesslist( successlist , SuccessSequence)
        ds = Dataset()
        ds.add(RetrievelUrlElement)
        ds.add(FailedSequence)
        ds.add(SuccessSequence)
        
        return ds.to_json()

    @staticmethod   
    def __buildJsonSuccesslist( successlist, SuccessSequence: DataElement ):

        successSeq = Sequence()
        for instance in successlist:

            instanceSOPClass = DataElement("00081150","UI", instance[0])
            instanceSOPInstanceUID = DataElement("00081155","UI", instance[1])
            instanceWadoUrl = DataElement("00081190","UR", instance[2])
            instanceDs = Dataset()
            instanceDs.add(instanceSOPClass)
            instanceDs.add(instanceSOPInstanceUID)
            instanceDs.add(instanceWadoUrl)

            if instance[3] is not None:
                instanceWarning = DataElement("00081196","US", instance[3])
                instanceDs.add(instanceWarning)


            successSeq.append(instanceDs)

        SuccessSequence.value = successSeq

        return SuccessSequence

    @staticmethod
    def __buildJsonFailedlist( failedlist, FailedSequence: DataElement):

        failedSeq = Sequence()
        for instance in failedlist:

            instanceSOPClass = DataElement("00081150","UI", instance[0])
            instanceSOPInstanceUID = DataElement("00081155","UI", instance[1])
            InstanceFailureReason = DataElement("00081197", "US" , instance[2])
            instanceDs = Dataset()
            instanceDs.add(instanceSOPClass)
            instanceDs.add(instanceSOPInstanceUID)
            instanceDs.add(InstanceFailureReason)
            
            failedSeq.append(instanceDs)

        FailedSequence.value = failedSeq

        return FailedSequence