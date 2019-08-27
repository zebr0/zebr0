import json
import logging

import boto3
import botocore.exceptions

import sts
import z0

logger = logging.getLogger("zebr0-aws.iam")
logger.info("creating iam client")
client = boto3.client(service_name="iam", region_name=z0.service.lookup("aws-region"))

user_name = z0.service.lookup("aws-user-name")
policy_name = z0.service.lookup("aws-policy-name")
policy_arn = "arn:aws:iam::" + sts.get_account_id() + ":policy/" + policy_name
bucket_arn = "arn:aws:s3:::" + z0.service.lookup("aws-bucket-name")


def get_policy():
    try:
        logger.info("checking policy")
        return client.get_policy(PolicyArn=policy_arn)
    except botocore.exceptions.ClientError as error:
        if error.response.get("Error").get("Code") != "NoSuchEntity":
            raise  # TODO


def create_policy_if_needed():
    if not get_policy():
        logger.info("creating policy")
        client.create_policy(PolicyName=policy_name,
                             PolicyDocument=json.dumps({
                                 "Version": "2012-10-17",
                                 "Statement": [{
                                     "Effect": "Allow",
                                     "Action": "s3:PutObject",
                                     "Resource": bucket_arn + "/*"
                                 }]
                             }))


def delete_policy_if_needed():
    if get_policy():
        logger.info("destroying policy")
        client.delete_policy(PolicyArn=policy_arn)


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

        logger.info("attaching policy to user")
        client.attach_user_policy(UserName=user_name, PolicyArn=policy_arn)


def delete_user_if_needed():
    if get_user():
        logger.info("detaching policy from user")
        client.detach_user_policy(UserName=user_name, PolicyArn=policy_arn)

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
