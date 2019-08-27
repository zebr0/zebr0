import logging

import boto3

import z0

logger = logging.getLogger("zebr0-aws.sts")
logger.info("creating sts client")
client = boto3.client(service_name="sts", region_name=z0.service.lookup("aws-region"))


def get_account_id():
    return client.get_caller_identity()["Account"]
