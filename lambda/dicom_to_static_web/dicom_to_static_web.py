import json
import io
import os
import pydicom
from pydicom import Dataset
from pydicom.dataelem import DataElement
from pydicom import uid
import boto3
import botocore
import uuid
from urllib.parse import unquote_plus
import logging
from pydicom import dcmread, dcmwrite
from pydicom.filebase import DicomFileLike

logger = logging.getLogger()
logger.setLevel(logging.INFO)

for var in ['VAR_DEBUG', 'VAR_OUTPUT_BUCKET', 'VAR_REGION', 'VAR_STATIC_DICOM_PREFIX', 'URI_PREFIX', 'MULTIPART_BOUNDARY_MARKER', 'VAR_DYNAMO_TABLE', 'VAR_DYNAMO_TABLE_SER']:
    if not var in os.environ:
        print(f"ERROR: Environment variable {var} not defined")
        exit(1)

debug = int(os.environ['VAR_DEBUG'])
bucket_out_name = os.environ['VAR_OUTPUT_BUCKET']
base_prefix = os.environ['VAR_STATIC_DICOM_PREFIX']
uri_prefix  = os.environ['URI_PREFIX']
boundary = os.environ['MULTIPART_BOUNDARY_MARKER']
dyn_table_name = os.environ['VAR_DYNAMO_TABLE']
dyn_ser_table_name = os.environ['VAR_DYNAMO_TABLE_SER']

study_base_prefix = ''

s3 = boto3.resource('s3', region_name=os.environ['VAR_REGION'])
s3c = boto3.client('s3', region_name=os.environ['VAR_REGION'])
dyn = boto3.resource('dynamodb')
table = dyn.Table(dyn_table_name)
table_ser = dyn.Table(dyn_ser_table_name)


# Aurora Serverless RDS
cluster = os.environ['CLUSTER_ARN']
secret = os.environ['SECRET_ARN']
db = os.environ['DB_NAME']
client = boto3.client('rds-data')

def lambda_handler(event, context):
   global study_base_prefix, bucket_out
   for record in event['Records']:
        bucket_in_name = record['s3']['bucket']['name']
        # unquote_plus is for handling objects with spaces in the names
        key = unquote_plus(record['s3']['object']['key'])
        logger.info('Processing object %s ',key )
        try:
            # Read S3 object into memory
            bucket_in = s3.Bucket(bucket_in_name)
            bucket_out = s3.Bucket(bucket_out_name)
            object = bucket_in.Object(key)
            file_stream = io.BytesIO()
            object.download_fileobj(file_stream)
            file_stream.seek(0)
            ds = pydicom.dcmread(file_stream)

        except BaseException as e:
            print('Cannot read dicom object: bucket name='+bucket_in_name+' key='+key)
            print(e)
        else:
            # Create Study Record
            study_base_prefix = create_study_record (ds, base_prefix, bucket_out, bucket_out_name)
            # Create Series Record
            series_key = create_series_record (ds, bucket_out, study_base_prefix)
            # Create Instances Records
            inst_key = create_instances_record (ds, bucket_out, series_key)
            #save pixel data 

            pixelDataPresent=write_frames(ds, bucket_out, inst_key)
            if((ds.Modality == 'SEG') or (pixelDataPresent == False)):
                write_NIO( ds, bucket_out, inst_key )


def create_study_record (ds, base_prefix, bucket_out, bucket_out_name):
    study_list_key = base_prefix + 'studies'
    study_prefix =study_list_key + '/' + ds.StudyInstanceUID
    std_uid = ds.StudyInstanceUID
    pat_name = ds.PatientName.family_comma_given()
    logger.info('..UID %s pat_name %s', std_uid,  pat_name)
    
    table.put_item(Item={
        'std_uid':      std_uid,
        'pat_name':     pat_name,
        'study_record': qido_rs_studies(ds)
    })
    sql = create_std_ser_sql(ds)
    response = client.execute_statement(
        database = db,
        secretArn = secret,
        resourceArn = cluster,
        sql = sql
    )
    logger.debug("--->Aurora Insert result %s", response)
    return study_prefix
    
def create_series_record (ds, bucket_out, std_pref):
    series_list_key = std_pref + '/series'
    series_prefix =series_list_key + '/' + ds.SeriesInstanceUID
    if not prefix_exists (bucket_out_name, series_prefix):
        #Add Series record to Series DynamoDB table
        ser_uid = ds.SeriesInstanceUID
        ser_number = str(ds.SeriesNumber)
        table_ser.put_item(Item={
            'ser_uid':          ser_uid,
            'ser_number':       ser_number,
            'study_record':     qido_rs_series(ds)
        })
        #update Series object structure in DicomWeb bucket
        if key_exists (bucket_out_name, series_list_key):
            obj = s3.Object(bucket_out_name, series_list_key)
            content = obj.get()['Body']
            json_data = json.load(content)
            jd_new = json.loads(qido_rs_series(ds))
            json_data.append(jd_new)
        else:
          json_data = []
          json_data.append(json.loads(qido_rs_series(ds)))
        js = json.dumps(json_data)
        bucket_out.put_object(Body=js, Key = series_list_key, ContentType = 'application/json')
    return series_prefix

def create_instances_record (ds, bucket_out, ser_key):
    instance_list_key = ser_key + '/instances'
    instance_meta_list_key = ser_key + '/metadata'
    instance_prefix = instance_list_key + '/' + ds.SOPInstanceUID
    instance_metadata_key = instance_prefix + '/metadata'
    if not prefix_exists (bucket_out_name, instance_prefix):
        if key_exists (bucket_out_name, instance_list_key):
            obj = s3.Object(bucket_out_name, instance_list_key)
            content = obj.get()['Body']
            json_data = json.load(content)
            jd_new = json.loads(qido_rs_instance(ds))
            json_data.append(jd_new)
        else:
          json_data = []
          json_data.append(json.loads(qido_rs_instance(ds)))
        js = json.dumps(json_data)
        bucket_out.put_object(Body=js, Key = instance_list_key, ContentType = 'application/json')

        if key_exists (bucket_out_name, instance_meta_list_key):
            obj = s3.Object(bucket_out_name, instance_meta_list_key)
            content = obj.get()['Body']
            json_data = json.load(content)
        else:
            json_data = []
        jd_new = json.loads(get_metadata(ds))
        json_data.append(jd_new)
        js = json.dumps(json_data)
        bucket_out.put_object(Body=js, Key = instance_meta_list_key, ContentType = 'application/json')

        #temp: put metadata list from series level on study level 
        study_meta_key = base_prefix + 'studies' + '/' + ds.StudyInstanceUID + '/metadata'

        bucket_out.put_object(Body=js, Key = study_meta_key, ContentType = 'application/json')
                
        json_data = []
        json_data.append(jd_new)
        js = json.dumps(json_data)
        bucket_out.put_object(Body=js, Key = instance_metadata_key, ContentType = 'application/json')

    return instance_prefix

def get_content_type (transfer_syntax):
    content_types = {
            uid.ImplicitVRLittleEndian:         "application/octet-stream",
            uid.ExplicitVRLittleEndian:         "application/octet-stream",
            uid.DeflatedExplicitVRLittleEndian: "application/octet-stream",
            uid.ExplicitVRBigEndian:            "application/octet-stream",
            uid.JPEGBaseline8Bit:               "image/jpeg",
            uid.JPEGExtended12Bit:              "image/jpeg",
            uid.JPEGLosslessP14:                "image/jpeg",
            uid.JPEGLosslessSV1:                "image/jpeg",
            uid.RLELossless:                    "image/dicom-rle",
            uid.JPEGLSLossless:                 "image/jls",
            uid.JPEGLSNearLossless:             "image/jls",
            uid.JPEG2000Lossless:               "image/jp2",
            uid.JPEG2000:                       "image/jp2",
            uid.JPEG2000MCLossless:             "image/jpx",
            uid.JPEG2000MC:                     "image/jpx",
            uid.MPEG2MPML:                      "video/mpeg2",
            uid.MPEG2MPHL:                      "video/mpeg2",
            uid.MPEG4HP41:                      "video/mp4",
            uid.MPEG4HP41BD:                    "video/mp4",
            uid.MPEG4HP422D:                    "video/mp4",
            uid.MPEG4HP423D:                    "video/mp4",
            uid.MPEG4HP42STEREO:                "video/mp4"
        }
    try:
        cont_type = content_types[transfer_syntax]
    except:
        cont_type = "application/octet-stream"
    return cont_type

def encode_multipart_object(transfer_syntax, object_bytes):
    hd = '--' + boundary + '\r\nContent-Type: '
    ct = get_content_type(transfer_syntax)
    tshd = '; transfer-syntax="'
    ts = transfer_syntax
    tsft = '"'
    crlf = '\r\n\r\n'
    ft = '\r\n--' + boundary + '--'
    multipart_frame =  hd.encode()
    multipart_frame += ct.encode()
    multipart_frame += tshd.encode()
    multipart_frame += ts.encode()
    multipart_frame += tsft.encode()
    multipart_frame += crlf.encode()
    multipart_frame += object_bytes
    multipart_frame += ft.encode()
    return multipart_frame

def write_NIO(ds, bucket_out, inst_key):
    print(f"[write_NIO] "+str(inst_key))
    try:
        transfer_syntax = ds.file_meta.TransferSyntaxUID
    except:
        transfer_syntax = '1.2.840.10008.1.2'
        if debug:
            print('TransferSyntaxUID not found')
    with io.BytesIO() as buffer:
        memory_dataset = DicomFileLike(buffer)
        dcmwrite(memory_dataset, ds)
        memory_dataset.seek(0)
        payload = memory_dataset.read()
    object_bytes = encode_multipart_object(transfer_syntax, payload)
    bucket_out.put_object(Body=object_bytes, Key = str(inst_key), ContentType = 'multipart/related; boundary="'+boundary+'"')
    return None

def write_frames (ds, bucket_out, i_key):
    instance_frame_key = str(i_key) + '/frames/'
    try:
        number_of_frames = ds['NumberOfFrames'].value
    except:
        number_of_frames = 1
        
    try:
        transfer_syntax = ds.file_meta.TransferSyntaxUID
    except:
        transfer_syntax = '1.2.840.10008.1.2'
        if debug:
            print('TransferSyntaxUID not found')

    #content_type = get_content_type(transfer_syntax)

    try:
        px_data = ds.data_element("PixelData")  # Get PixelData data element to check data length
    except:
        # DICOM object has no pixel data, could be Presentation State, RT object or another non-image object
        logger.info("No Pixel data found ")
        return False

    if px_data.is_undefined_length:   
        # Encapsulated compressed image
        if debug:
            print('Encapsulated compressed image. Transfer syntax = ' + ds.file_meta.TransferSyntaxUID)
        generator = pydicom.encaps.generate_pixel_data_frame(ds.PixelData, number_of_frames)
        fr_ind = 1
        for encoded_frame in generator:  # each frame is a compressed image
            print('====type of encoded frame = ' + str(type(encoded_frame)))
            multipart_frame = encode_multipart_object(transfer_syntax, encoded_frame)
            bucket_out.put_object(Body=multipart_frame, Key = instance_frame_key+str(fr_ind), ContentType = 'multipart/related; boundary="'+boundary+'"')
    else:
        # Native image
        try:
            r = int(ds.Rows)
            c = int(ds.Columns)
            spp = int(ds.SamplesPerPixel)
            ba = int(ds.BitsAllocated)
            fr_size = int(r * c * spp * (ba / 8))
        except BaseException as err:
            print ('calculating frame size...')
            print(err)

        for fr_ind in range(number_of_frames):
            ind_from =int(fr_ind * fr_size)
            ind_to =  min (int((fr_ind + 1) * fr_size), len(ds.PixelData))

            # check the end of buffer
            if len(ds.PixelData) < int((fr_ind + 1) * fr_size):
                    print('PixelData length '+str(len(ds.PixelData))+' is too short. Frame #'+str(fr_ind)+'expected end '+str(int((fr_ind + 1)*fr_size)))
            multipart_frame = encode_multipart_object(transfer_syntax, ds.PixelData[ind_from:ind_to])
            bucket_out.put_object(Body=multipart_frame, Key = instance_frame_key+ str(fr_ind+1), ContentType = 'multipart/related; boundary="'+boundary+'"')
    return True

def qido_rs_series(ds):
    series_attr=[[0x0008,0x0005,'SpecificCharacterSet'],            # Specific Character Set 
                [0x0008,0x0021,'SeriesDate'],
                [0x0008,0x0031,'SeriesTime'],
                [0x0008,0x0060,'Modality'],                         # Modality 
                [0x0008,0x0201,'TimezoneOffsetFromUTC'],            # Timezone Offset From UTC 
                [0x0008,0x103E,'SeriesDescription'],                # Series Description 
                [0x0020,0x000D,'StudyInstanceUID'],                 # Study Instance UID 
                [0x0020,0x000E,'SeriesInstanceUID'],                # Series Instance UID 
                [0x0020,0x0011,'SeriesNumber'],                     # Series Number 
                [0x0020,0x1209,'NumberOfSeriesRelatedInstances'],   # Number of Series Related Instances 
                [0x0040,0x0244,'PerformedProcedureStepStartDate'],  # Performed Procedure Step Start Date
                [0x0040,0x0245,'PerformedProcedureStepStartTime'],  # Performed Procedure Step Start Time
                [0x0040,0x0275,'RequestAttributeSequence']]         # Request Attribute Sequence 

    json_data = get_dicom_attributes(ds, series_attr)
    return json_data
    
def qido_rs_studies(ds):
    series_attr=[[0x0008,0x0005,'SpecificCharacterSet'],            # Specific Character Set 
                [0x0008,0x0020,'StudyDate'],
                [0x0008,0x0030,'StudyTime'],
                [0x0008,0x0050,'AccessionNumber'],
                [0x0008,0x0061,'ModalitiesInStudy'],                        
                [0x0008,0x1030,'StudyDescription'],
                [0x0010,0x0010,'PatientName'],            
                [0x0010,0x0020,'PatientID'],               
                [0x0010,0x1010,'PatientAge'],            
                [0x0020,0x000D,'StudyInstanceUID'],              
                [0x0020,0x0010,'StudyID'],             
                [0x0020,0x1206,'NumberOfStudyRelatedSeries'],   
                [0x0020,0x1208,'NumberOfStudyRelatedInstances']]          

    json_data = get_dicom_attributes(ds, series_attr)
    return json_data

def qido_rs_instance(ds):
    series_attr=[[0x0008,0x0016,'SOPClassUID'],
                [0x0008,0x0018,'SOPInstanceUID'],
                [0x0008,0x0023,'ContentDate'],
                [0x0008,0x0033,'ContentTime'],
                [0x0008,0x3002,'AvailableTransferSyntaxUID'],                        
                [0x0020,0x000D,'StudyInstanceUID'],              
                [0x0020,0x000E,'SeriesInstanceUID'],             
                [0x0020,0x0013,'InstanceNumber'],   
                [0x0028,0x0010,'Rows'],
                [0x0028,0x0011,'Columns']]          

    json_data = get_dicom_attributes(ds, series_attr)
    return json_data 

def get_dicom_element_val(ds, tag_name):
    try:
        val = ds[tag_name].repval
        vr = ds[tag_name].VR
        logger.debug(':::element %s=<%s> VR=%s', tag_name, val, vr)
        if vr == 'UI':
            return "'" + val + "'"
        else:
            return val
    except:
        return ''
    
def create_std_ser_sql(ds):
    # DICOM attribute name and DB taable name
    attrs = [
                ['StudyDate','study_date'],
                ['StudyTime','study_time'],
                ['AccessionNumber','accession_number'],
                ['Modality','modality'],
                ['ModalitiesInStudy','modalities_in_std'],                      
                ['StudyDescription','study_description'],
                ['PatientName','patient_name'],   
                ['PatientID','patient_id'],            
                ['StudyInstanceUID','study_instance_uid'], 
                ['SeriesInstanceUID','series_instance_uid'],
                ['StudyID','study_id'],
                ['SeriesNumber','series_number'],
                ['SeriesDescription','series_description']
            ]          

    sql = 'INSERT INTO study_series ('
    values = ''
    for attr in attrs:
        #logger.info('-->loop on attrs. attr=%s attr[0]=%s attr[1]=%s', attr, attr[0], attr[1])
        val = get_dicom_element_val(ds, attr[0])
        #logger.info('----> Element %s val %s, type of val=%s',attr[0], val, type(val))
        if val:
            sql += attr[1] + ','
            values += val + ',' 
            
    sql = sql[:-1] + ') VALUES ('+ values
    sql = sql[:-1] + ') ON CONFLICT (study_instance_uid, series_instance_uid) DO NOTHING'
    logger.debug("--->sql insert %s", sql)
    return sql
    
def get_metadata(ds):
    json_data = ds.to_json(bulk_data_element_handler=bulk_data_handler)
    #if debug :
       # print ('json_data  = ' + json_data)
    return json_data

def bulk_data_handler(de):
    bulk_object_key = study_base_prefix  + '/bulk_data/' + str(uuid.uuid4())
    bucket_out.put_object(Body=de.value, Key = bulk_object_key, ContentType = 'application/octet-stream')
    uri = uri_prefix + "/" + bulk_object_key 
    return uri

def get_dicom_attributes(ds, attr):
    json_data = ''
    subset = Dataset()
    for elm in attr:
        try:
            s = elm[2]
            e = ds[s]
            subset.add(e)
        except:
            if debug: 
                logger.debug("Element " + elm[2] +' not found')
            if elm[2] == 'ModalitiesInStudy':
                # We do not have profiling and tag morphing features. For studies without Modalities)nStudy element we will insert modalitiy values in QidoQuery.
                # add element with placeholder value. Qido Query Lambda will replace it with list of modalieites in study.
                elem = DataElement([elm[0], elm[1]],'CS','REPLACEME')
                subset.add(elem)
            pass
    json_data = subset.to_json(bulk_data_element_handler=bulk_data_handler)
    logger.debug('--> get_dicom_attributes json_data type = ' + str(type(json_data)) +'   data='+json_data)
    return json_data

def key_exists(bucket, key):
    try:
        metadata = s3c.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as e:
        if e.response['Error']['Code']=='404':
            return False
        else:
            raise e
        
def prefix_exists(bucket, prefix):
    results = s3c.list_objects(Bucket=bucket, Prefix=prefix)
    return 'Contents' in results
    