import logging

import boto3
import botocore.exceptions

import z0

logger = logging.getLogger("zebr0-aws.s3")

region = z0.service.lookup("aws-region")
logger.info("creating s3 client")
client = boto3.client(service_name="s3", region_name=region)
bucket_name = z0.service.lookup("aws-bucket-name")


def head_bucket():
    try:
        logger.info("checking bucket")
        client.head_bucket(Bucket=bucket_name)
        return True
    except botocore.exceptions.ClientError as error:
        if error.response.get("Error").get("Code") == "404":
            return False
        else:
            raise  # TODO


def create_bucket_if_needed():
    if not head_bucket():
        logger.info("creating bucket")
        client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": region}
        )
