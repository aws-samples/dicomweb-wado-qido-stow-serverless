import json
import logging
import os
import boto3
import re
from boto3.dynamodb.conditions import Key, Attr

for var in ['VAR_DEBUG', 'VAR_DYNAMO_TABLE']:
    if not var in os.environ:
        print(f"ERROR: Environment variable {var} not defined")
        exit(1)


dyn_table_name = os.environ['VAR_DYNAMO_TABLE']
dyn_ser_table_name = os.environ['VAR_DYNAMO_TABLE_SER']
dyn = boto3.resource('dynamodb')
table = dyn.Table(dyn_table_name)
ser_table = dyn.Table(dyn_ser_table_name)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
 
cluster = os.environ['CLUSTER_ARN']
secret = os.environ['SECRET_ARN']
db = os.environ['DB_NAME']
client = boto3.client('rds-data')

def lambda_handler(event, context):

    response_code = 200
    response = {}
    http_method = event['httpMethod']
    query_path_full = event["path"]
    query_path = query_path_full.replace("/qido", "", 1)
    query_string = event['queryStringParameters']
    if query_string is None: query_string = {}
    logger.info('http method %s query_path=<%s> query_string %s',http_method, query_path, query_string)

    if http_method == 'GET':
        #
        # Identify QIDO Search Transaction Resource
        #
        if query_path == '/studies':
            res = qido_all_std(query_string)
        elif query_path == '/series':
            res = qido_all_ser(query_string) 
        else:
            pattern = re.compile("/studies/(?P<uid>[^/]*)/series$")
            match = pattern.match(query_path)
            if match:
                std_uid = match.group("uid")
                res = qido_all_ser(query_string, std_uid)
            else:
                response_code = 400
                logger.error('QIDO search transaction resource not supported. Resource path specified <%s>', query_path)
                res = ""
                
        response = {
            'statusCode': response_code,
            'headers': { 
                'Content-Type': 'application/json',
                'Access-Control-Allow-Headers': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': str(res)
        }
    else:
        greeting = f"Sorry, {http_method} isn't allowed."
        response_code = 405

    logger.info("Response: %s", response)
    return response
    
def check_and_fill_modalities(std_rec_str, uid):
    std_rec = std_rec_str
    ignore_list = ['PR','RTDOSE','RTSTRUCT','RTIMAGE','RTPLAN']
    logger.info('===>str = %s', std_rec_str)
    if 'REPLACEME' in std_rec_str:
        # We planted 'REPLACEME' in ModalitiesInStudy element. Now we will replace it with a list of modalities
        sql_query = "SELECT DISTINCT modality FROM study_series WHERE study_instance_uid = '"+ uid +"'"
        logger.debug('sql_query = %s', sql_query)
        rsp = client.execute_statement(database=db, secretArn=secret, resourceArn=cluster, sql=sql_query)
        mod_in_std = ''
        for rec in rsp['records']:
            mod = rec[0]['stringValue']
            logger.info('...mod = %s type %s', mod, type(mod))
            if not mod in ignore_list:
                if mod_in_std:
                    mod_in_std += ','
                # mod_in_std += '"'+mod+'"'
                mod_in_std += mod
        std_rec = std_rec_str.replace('REPLACEME', mod_in_std)
        logger.debug('...std_rec = %s ', std_rec)
    return str(std_rec)

def build_std_sql(attrs):
    # dictionary of DICOM attribute names and Database column names
    db_attrs ={
                'AccessionNumber':      'accession_number',
                'StudyDescription':     'study_description',
                'PatientName':          'patient_name',   
                'PatientID':            'patient_id',            
                'StudyID':              'study_id'
        }
    sql_query = 'SELECT DISTINCT study_instance_uid FROM study_series '
    where_clause = False
    attr_keys = attrs.keys()
    logger.debug("Keys = %s",str(attr_keys))
    for key in attr_keys:
        logger.debug("Key = %s",key)
        condition = ''
        if key in db_attrs.keys():
            condition = db_attrs[key] + " ILIKE '" + attrs[key].replace('*','%') + "'"
            logger.info("Condition = %s", condition)
        elif key == 'ModalitiesInStudy':
            modalities = attrs[key].split(',')
            condition = "modality IN ("
            for mod in modalities:
                condition += "'" + mod + "',"
            condition = condition[:-1] +")"
        elif key == 'StudyInstanceUID':
            condition = " study_instance_uid = '" + attrs[key] + "' "

        if condition and where_clause:
            sql_query += " AND " + condition
        elif condition:
            sql_query += " WHERE " + condition
            where_clause = True
    if 'limit' in attr_keys:
        sql_query += ' LIMIT ' + attrs['limit']
    if 'offset' in attr_keys:
        sql_query += ' OFFSET ' + attrs['offset']
    else:
        sql_query += ' LIMIT 100'   # default limit *on # of records in query
    logger.info('---> SQL query %s', sql_query)
    return sql_query
    
def qido_all_std(attrs):
    sql_query = build_std_sql(attrs)
    response = client.execute_statement(database=db, secretArn=secret, resourceArn=cluster, sql=sql_query)
    logger.debug("--->Aurora Query result %s %s", type(response), response)
    
    res = ''
    for rec in response['records']:
        uid = rec[0]['stringValue']
        logger.info('uid = %s', uid)
        db_res = table.query(KeyConditionExpression=Key('std_uid').eq(uid))

        item = db_res['Items'][0]
        logger.debug("item['study_record']=%s",item['study_record'])
        record = check_and_fill_modalities(item['study_record'], uid)
        #record = item['study_record']
        if res:
            res += ','
        else:
            res = '['
        res += record

    if res: res+= ']'
    #logger.info("res[]: %s",res)
    return res
    
def build_ser_sql(attrs, std_uid):
    # dictionary of DICOM attribute names and Database column names
    db_attrs ={
                'AccessionNumber':      'accession_number',
                'StudyDescription':     'study_description',
                'PatientName':          'patient_name',   
                'PatientID':            'patient_id',            
                'StudyID':              'study_id',
                'Modality':             'modality',
                'SeriesNumber':         'series_number',
                'StudyInstanceUID':     'study_instance_uid',
                'SeriesInstanceUID':    'series_instance_uid'
        }
    sql_query = 'SELECT series_instance_uid FROM study_series '
    where_clause = False
    attr_keys = attrs.keys()
    logger.debug("Keys = %s",str(attr_keys))
    
    # process study UID if supplied
    if std_uid:
        sql_query += " WHERE study_instance_uid = '" + std_uid + "'"
        where_clause = True

    for key in attr_keys:
        logger.debug("Key = %s",key)
        condition = ''
        if key in db_attrs.keys():
            condition = db_attrs[key] + " ILIKE '" + attrs[key].replace('*','%') + "'"
            logger.info("Condition = %s", condition)
        if condition and where_clause:
            sql_query += " AND " + condition
        elif condition:
            sql_query += " WHERE " + condition
            where_clause = True
    if 'limit' in attr_keys:
        sql_query += ' LIMIT ' + attrs['limit']
    else:
        sql_query += ' LIMIT 100'   # default limit on # of records in query
    if 'offset' in attr_keys:
        sql_query += ' OFFSET ' + attrs['offset']
    logger.debug('---> SQL query %s', sql_query)
    return sql_query
   
def qido_all_ser(attrs, std_uid = ''):
    sql_query = build_ser_sql(attrs, std_uid)
    response = client.execute_statement(
        database = db,
        secretArn = secret,
        resourceArn = cluster,
        sql = sql_query
    )
    logger.debug("--->Aurora Query result %s %s", type(response), response)
    
    res = ''
    for rec in response['records']:
        uid = rec[0]['stringValue']
        logger.info('uid = %s', uid)
        db_res = ser_table.query(
            KeyConditionExpression=Key('ser_uid').eq(uid)
        )
        logger.debug("--->Dynamo Query result %s %s", type(db_res), db_res)

        item = db_res['Items'][0]
        logger.debug("item['study_record']=%s",item['study_record'])
        record = item['study_record']
        if res:
            res += ','
        else:
            res = '['
        res += record

    if res: res += ']'
    # logger.info("res[]: %s",res)
    return res
