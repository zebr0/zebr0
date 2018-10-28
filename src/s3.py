import logging

import boto3
import botocore.exceptions


class Service:
    def __init__(self, zebr0_service):
        self.zebr0_service = zebr0_service

        self.logger = logging.getLogger("zebr0-aws.s3")

        self.region = self.zebr0_service.lookup("aws-region")
        self.logger.info("creating s3 client")
        self.client = boto3.client(service_name="s3", region_name=self.region)
        self.bucket_name = self.zebr0_service.lookup("aws-bucket-name")

    def head_bucket(self):
        try:
            self.logger.info("checking bucket")
            self.client.head_bucket(Bucket=self.bucket_name)
            return True
        except botocore.exceptions.ClientError as error:
            if error.response.get("Error").get("Code") == "404":
                return False
            else:
                raise  # TODO

    def create_bucket_if_needed(self):
        if not self.head_bucket():
            self.logger.info("creating bucket")
            self.client.create_bucket(
                Bucket=self.bucket_name,
                CreateBucketConfiguration={'LocationConstraint': self.region}
            )

    def destroy_bucket_if_needed(self):
        if self.head_bucket():
            self.logger.info("destroying bucket")
            self.client.delete_bucket(Bucket=self.bucket_name)
