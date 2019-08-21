import logging

import boto3
import botocore.exceptions

import z0

logger = logging.getLogger("zebr0-aws.iam")
logger.info("creating iam client")
client = boto3.client(service_name="iam", region_name=z0.service.lookup("aws-region"))

user_name = z0.service.lookup("aws-user-name")


def get_user():
    try:
        logger.info("checking user")
        return client.get_user(UserName=user_name)
    except botocore.exceptions.ClientError as error:
        if error.response.get("Error").get("Code") != "NoSuchEntity":
            raise  # TODO


def create_user_if_needed():
    if not get_user():
        logger.info("creating user")
        client.create_user(UserName=user_name)


def delete_user_if_needed():
    if get_user():
        logger.info("destroying user")
        client.delete_user(UserName=user_name)


def delete_old_access_keys():
    current_access_key_id = boto3.DEFAULT_SESSION.get_credentials().access_key

    try:
        for access_key in client.list_access_keys(UserName=user_name).get("AccessKeyMetadata"):
            access_key_id = access_key.get("AccessKeyId")
            if access_key_id != current_access_key_id:
                logger.info("destroying old access key '%s'", access_key_id)
                client.delete_access_key(UserName=user_name, AccessKeyId=access_key_id)
    except botocore.exceptions.ClientError as error:
        if error.response.get("Error").get("Code") != "NoSuchEntity":
            raise  # TODO


def create_access_key():
    logger.info("creating access key")
    return client.create_access_key(UserName=user_name).get("AccessKey")
