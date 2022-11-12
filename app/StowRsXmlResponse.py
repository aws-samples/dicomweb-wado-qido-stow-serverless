"""
StowRsXmlResponse.py : a class used to build a DICOM PS18 STOW-RS response enveloppe in XML.

SPDX-License-Identifier: Apache 2.0
"""

import xml.etree.ElementTree as ET

class StowRsXmlResponse(object):
    
    @staticmethod
    def generateResponse( successlist , failedlist, retrieveUrl):
        data = ET.Element('NativeDicomModel')

        data.set("xlmns","http://dicom.nema.org/PS3.19/models/NativeDICOM")
        data.set("xsi:schemaLocation","http://dicom.nema.org/PS3.19/models/NativeDICOM")
        data.set("xmlns:xsi","http://www.w3.org/2001/XMLSchema-instance")

        RetrieveUrlAttribute = ET.SubElement(data, 'DicomAttribute')
        RetrieveUrlAttribute.set('tag','00081190')
        RetrieveUrlAttribute.set('vr','UR')
        RetrieveUrlAttribute.set('keyword','RetrieveURL')

        RetrieveUrlAttribute = StowRsXmlResponse.__buildXMLRetrieveUrl(retrieveUrl, RetrieveUrlAttribute)

        FailedDICOMAttribute = ET.SubElement(data, 'DicomAttribute')
        FailedDICOMAttribute.set('tag','00081198')
        FailedDICOMAttribute.set('vr','SQ')
        FailedDICOMAttribute.set('keyword','FailedSOPSequence')

        FailedDICOMAttribute = StowRsXmlResponse.__buildXMLFailedlist(failedlist, FailedDICOMAttribute)


        ReferencedDICOMAttribute = ET.SubElement(data, 'DicomAttribute')
        ReferencedDICOMAttribute.set('tag','00081199')
        ReferencedDICOMAttribute.set('vr','SQ')
        ReferencedDICOMAttribute.set('keyword','ReferencedSOPSequence') 

        
        ReferencedDICOMAttribute = StowRsXmlResponse.__buildXMLSuccesslist(successlist, ReferencedDICOMAttribute)
      

        return ET.tostring(data)

    @staticmethod
    def __buildXMLRetrieveUrl( retrieveUrl , RetrieveUrlAttribute):
        instanceNumber=1
        ItemElem = ET.SubElement(RetrieveUrlAttribute, "Value")
        ItemElem.set("number", str(instanceNumber))
        ItemElem.text = retrieveUrl

        return RetrieveUrlAttribute

    @staticmethod   
    def __buildXMLSuccesslist( successlist, ReferencedDICOMAttribute):
        SuccessinstanceNumber=1

        for instance in successlist:
            
            ItemElem = ET.SubElement(ReferencedDICOMAttribute, "Item")
            ItemElem.set("number", str(SuccessinstanceNumber))

            InstanceDICOMAttribute = ET.SubElement(ItemElem, "DicomAttribute")
            InstanceDICOMAttribute.set('tag','00081150')
            InstanceDICOMAttribute.set('vr','UI')
            InstanceDICOMAttribute.set('keyword','ReferencedSOPClassUID')
            ValueElem = ET.SubElement(InstanceDICOMAttribute, "Value")
            ValueElem.set("number",str(1))
            ValueElem.text = instance[0]


            InstanceDICOMAttribute = ET.SubElement(ItemElem, "DicomAttribute")
            InstanceDICOMAttribute.set('tag','00081155')
            InstanceDICOMAttribute.set('vr','UI')
            InstanceDICOMAttribute.set('keyword','ReferencedSOPInstanceUID')
            ValueElem = ET.SubElement(InstanceDICOMAttribute, "Value")
            ValueElem.set("number",str(1))
            ValueElem.text = instance[1]  


            InstanceDICOMAttribute = ET.SubElement(ItemElem, "DicomAttribute")
            InstanceDICOMAttribute.set('tag','00081190')
            InstanceDICOMAttribute.set('vr','UR')
            InstanceDICOMAttribute.set('keyword','RetrieveURL')
            ValueElem = ET.SubElement(InstanceDICOMAttribute, "Value")
            ValueElem.set("number",str(1))
            ValueElem.text = instance[2]  

            if( instance[3] is not None):
                InstanceDICOMAttribute = ET.SubElement(ItemElem, "DicomAttribute")
                InstanceDICOMAttribute.set('tag','00081196')
                InstanceDICOMAttribute.set('vr','US')
                InstanceDICOMAttribute.set('keyword','WarningReason')
                ValueElem = ET.SubElement(InstanceDICOMAttribute, "Value")
                ValueElem.set("number",str(1))
                ValueElem.text = instance[2]  

            SuccessinstanceNumber+=1
        return ReferencedDICOMAttribute

    @staticmethod
    def __buildXMLFailedlist( failedlist, FailedDICOMAttribute):
        FailedinstanceNumber=1
        for instance in failedlist:

            ItemElem = ET.SubElement(FailedDICOMAttribute, "Item")
            ItemElem.set("number", str(FailedinstanceNumber))

            InstanceDICOMAttribute = ET.SubElement(ItemElem, "DicomAttribute")
            InstanceDICOMAttribute.set('tag','00081150')
            InstanceDICOMAttribute.set('vr','UI')
            InstanceDICOMAttribute.set('keyword','ReferencedSOPClassUID')
            ValueElem = ET.SubElement(InstanceDICOMAttribute, "Value")
            ValueElem.set("number",str(1))
            ValueElem.text = instance[0]


            InstanceDICOMAttribute = ET.SubElement(ItemElem, "DicomAttribute")
            InstanceDICOMAttribute.set('tag','00081155')
            InstanceDICOMAttribute.set('vr','UI')
            InstanceDICOMAttribute.set('keyword','ReferencedSOPInstanceUID')
            ValueElem = ET.SubElement(InstanceDICOMAttribute, "Value")
            ValueElem.set("number",str(1))
            ValueElem.text = instance[1]  


            InstanceDICOMAttribute = ET.SubElement(ItemElem, "DicomAttribute")
            InstanceDICOMAttribute.set('tag','00081197')
            InstanceDICOMAttribute.set('vr','US')
            InstanceDICOMAttribute.set('keyword','FailureReason')
            ValueElem = ET.SubElement(InstanceDICOMAttribute, "Value")
            ValueElem.set("number",str(1))
            ValueElem.text = instance[2]             
            
            FailedinstanceNumber+=1

        return FailedDICOMAttribute