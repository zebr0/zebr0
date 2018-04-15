#!/usr/bin/python3 -u

import argparse
import pprint

import boto3

region = "eu-central-1"
user_data = """
#cloud-config
runcmd:
  - echo "{}" > /etc/projectname
  - echo "{}" > /etc/stagename
  - wget -O- https://raw.githubusercontent.com/mazerty/idem/master/install.sh | sh
  - idem.py run aws
power_state:
  mode: reboot
"""

session = boto3.Session(region_name=region)
ec2_client = session.client("ec2")
route53_client = session.client("route53")
s3_client = session.client("s3")


class Instance:
    def __init__(self, instance):
        def get_tag_value(key, instance):
            return next(map(
                lambda tag: tag.get("Value"),
                filter(
                    lambda tag: tag.get("Key") == key,
                    instance.get("Tags", [])
                )
            ), None)

        self.id = instance.get("InstanceId")
        self.launch_time = instance.get("LaunchTime")
        self.state = instance.get("State").get("Name")
        self.ip = instance.get("PublicIpAddress")
        self.project = get_tag_value("project", instance)
        self.stage = get_tag_value("stage", instance)

    def __str__(self):
        return " ".join(map(str, filter(
            lambda attr: attr is not None,
            [self.id, self.launch_time, self.state, self.ip, self.project, self.stage]
        )))


def _get_instance(parameters):
    reservations = ec2_client.describe_instances(**parameters).get("Reservations")
    return reservations[0].get("Instances")[0] if reservations else None


def get_instance(project, stage):
    return _get_instance(dict(Filters=[
        {"Name": "tag:project", "Values": [project]},
        {"Name": "tag:stage", "Values": [stage]},
        {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}
    ]))


def get_instance_by_id(instance_id):
    return _get_instance(dict(InstanceIds=[instance_id]))


def change_record_set(project, stage, ip, action):
    route53_client.change_resource_record_sets(
        HostedZoneId=route53_client.list_hosted_zones().get("HostedZones")[0].get("Id"),
        ChangeBatch={"Changes": [{
            "Action": action,
            "ResourceRecordSet": {
                "Name": ".".join([stage, project, "mazerty.fr"]),
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": ip}]
            }
        }]}
    )


def status(args):
    for reservation in ec2_client.describe_instances().get("Reservations"):
        for instance in reservation.get("Instances"):
            pprint.pprint(instance) if args.full else print(Instance(instance))


def run(args):
    if get_instance(args.project, args.stage):
        print("error: instance already exists")
        exit(1)

    instance_id = ec2_client.run_instances(
        ImageId="ami-97e953f8",
        MinCount=1,
        MaxCount=1,
        KeyName="keypair",
        InstanceType="t2.micro",
        UserData=user_data.format(args.project, args.stage)
    ).get("Instances")[0].get("InstanceId")
    ec2_client.create_tags(
        Resources=[instance_id],
        Tags=[{"Key": "project", "Value": args.project},
              {"Key": "stage", "Value": args.stage}]
    )

    instance = Instance(get_instance(args.project, args.stage))
    change_record_set(args.project, args.stage, instance.ip, "CREATE")

    bucket_name = ".".join(["mazerty", args.project, args.stage])
    if not any(filter(
            lambda bucket: bucket.get("Name") == bucket_name,
            s3_client.list_buckets().get("Buckets")
    )):
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': region}
        )

    print(instance)


def terminate(args):
    instance = get_instance(args.project, args.stage)
    if not instance:
        print("error: instance does not exist")
        exit(1)

    instance_id = instance.get("InstanceId")
    ec2_client.terminate_instances(InstanceIds=[instance_id])

    instance = Instance(get_instance_by_id(instance_id))
    change_record_set(args.project, args.stage, instance.ip, "DELETE")
    print(instance)


def s3_status(args):
    for bucket in s3_client.list_buckets().get("Buckets"):
        print(bucket.get("CreationDate"), bucket.get("Name"))


def s3_delete(args):
    s3_client.delete_bucket(Bucket=args.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_status = subparsers.add_parser("status")
    parser_status.add_argument("--full", action="store_true")
    parser_status.set_defaults(func=status)

    parser_run = subparsers.add_parser("run")
    parser_run.add_argument("project", nargs="?")
    parser_run.add_argument("stage", nargs="?", default="master")
    parser_run.set_defaults(func=run)

    parser_terminate = subparsers.add_parser("terminate")
    parser_terminate.add_argument("project", nargs="?")
    parser_terminate.add_argument("stage", nargs="?")
    parser_terminate.set_defaults(func=terminate)

    parser_s3 = subparsers.add_parser("s3")
    subparsers_s3 = parser_s3.add_subparsers()

    parser_s3_status = subparsers_s3.add_parser("status")
    parser_s3_status.set_defaults(func=s3_status)

    parser_s3_delete = subparsers_s3.add_parser("delete")
    parser_s3_delete.add_argument("name", nargs="?")
    parser_s3_delete.set_defaults(func=s3_delete)

    args = parser.parse_args()

    args.func(args)
