import boto3
import sys
import re
import json
from collections import defaultdict
from urllib.parse import unquote_plus


def get_kv_map(file_name, bucket):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucket)

    bytes_test = None
    for obj in bucket.objects.all():
        print(obj.key)
        if obj.key == file_name:
            body = obj.get()['Body'].read()
            bytes_test = bytearray(body)
            print('Image loaded', file_name)
            break

    # process using image bytes
    session = boto3.Session()
    client = session.client('textract', region_name='us-west-2')
    response = client.analyze_document(Document={'Bytes': bytes_test}, FeatureTypes=['FORMS'])

    # Get the text blocks
    blocks = response['Blocks']

    # get key and value maps
    key_map = {}
    value_map = {}
    block_map = {}
    for block in blocks:
        block_id = block['Id']
        block_map[block_id] = block
        if block['BlockType'] == "KEY_VALUE_SET":
            if 'KEY' in block['EntityTypes']:
                key_map[block_id] = block
            else:
                value_map[block_id] = block

    return key_map, value_map, block_map


def get_kv_relationship(key_map, value_map, block_map):
    kvs = defaultdict(list)
    for block_id, key_block in key_map.items():
        value_block = find_value_block(key_block, value_map)
        key = get_text(key_block, block_map)
        val = get_text(value_block, block_map)
        kvs[key].append(val)
    return kvs


def find_value_block(key_block, value_map):
    for relationship in key_block['Relationships']:
        if relationship['Type'] == 'VALUE':
            for value_id in relationship['Ids']:
                value_block = value_map[value_id]
    return value_block


def get_text(result, blocks_map):
    text = ''
    if 'Relationships' in result:
        for relationship in result['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    word = blocks_map[child_id]
                    if word['BlockType'] == 'WORD':
                        text += word['Text'] + ' '
                    if word['BlockType'] == 'SELECTION_ELEMENT':
                        if word['SelectionStatus'] == 'SELECTED':
                            text += 'X '

    return text


def print_kvs(kvs):
    for key, value in kvs.items():
        print(key, ":", value)


def search_value(kvs, search_key):
    for key, value in kvs.items():
        if re.search(search_key, key, re.IGNORECASE):
            return value


def lambda_handler(event, context):
    file_obj = event["Records"][0]
    bucket = unquote_plus(str(file_obj["s3"]["bucket"]["name"]))
    file_name = unquote_plus(str(file_obj["s3"]["object"]["key"]))

    key_map, value_map, block_map = get_kv_map(file_name, bucket)
    kvs = get_kv_relationship(key_map, value_map, block_map)
    print("\n\n== FOUND KEY : VALUE pairs ===\n")
    print_kvs(kvs)

    # Amazon Textract client
    # textract = boto3.client('textract', region_name='us-west-2')

    # Call Amazon Textract
    '''
    response = textract.detect_document_text(
        Document={
            'S3Object': {
                'Bucket': bucket,
                'Name': file_name
            }
        }
    )
    '''

    '''
    blocks = response['Blocks']
    # print(f'BLOCKS: {blocks}')

    key_map = {}
    value_map = {}
    block_map = {}
    for block in blocks:
        block_id = block['Id']
        if 'Text' in block:
            block_text = block['Text']
            print(f'ID: {block_id}, Text: {block_text}')
    '''