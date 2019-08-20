import json
import logging

import boto3
import jinja2

import z0

logger = logging.getLogger("zebr0-aws.ec2")

region = z0.service.lookup("aws-region")
logger.info("creating ec2 client")
client = boto3.client(service_name="ec2", region_name=region)

default_filters = [{"Name": "tag:project", "Values": [z0.service.project]},
                   {"Name": "tag:stage", "Values": [z0.service.stage]}]


def describe_vpc():
    logger.info("checking vpc")
    vpcs = client.describe_vpcs(Filters=default_filters).get("Vpcs")
    return vpcs[0] if vpcs else None


def describe_subnet():
    logger.info("checking subnet")
    subnets = client.describe_subnets(Filters=default_filters).get("Subnets")
    return subnets[0] if subnets else None


def describe_instance():
    logger.info("checking instance")
    filters = default_filters + [{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
    reservations = client.describe_instances(Filters=filters).get("Reservations")
    return reservations[0].get("Instances")[0] if reservations else None


def describe_internet_gateway():
    logger.info("checking internet gateway")
    internet_gateways = client.describe_internet_gateways(Filters=default_filters).get("InternetGateways")
    return internet_gateways[0] if internet_gateways else None


def describe_address():
    logger.info("checking address")
    addresses = client.describe_addresses(Filters=default_filters).get("Addresses")
    return addresses[0] if addresses else None


def create_tags(resource_id):
    logger.info("updating resource tags")
    client.create_tags(Resources=[resource_id], Tags=[{"Key": "project", "Value": z0.service.project},
                                                      {"Key": "stage", "Value": z0.service.stage}])


def create_vpc_if_needed():
    vpc = describe_vpc()

    if not vpc:
        network_cidr = z0.service.lookup("aws-network-cidr")

        logger.info("creating vpc")
        create_vpc = client.create_vpc(CidrBlock=network_cidr)
        vpc_id = create_vpc.get("Vpc").get("VpcId")
        client.get_waiter("vpc_exists").wait(VpcIds=[vpc_id])
        create_tags(vpc_id)

        logger.info("checking security group")
        security_groups = client.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("SecurityGroups")

        logger.info("adding ingress permissions")
        client.authorize_security_group_ingress(
            GroupId=security_groups[0].get("GroupId"),
            IpPermissions=[
                {"FromPort": 80, "ToPort": 80, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"FromPort": 2501, "ToPort": 2501, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"FromPort": 2502, "ToPort": 2502, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"FromPort": -1, "ToPort": -1, "IpProtocol": "icmp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"FromPort": 22, "ToPort": 22, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}  # TODO
            ]
        )

        return vpc_id
    else:
        return vpc.get("VpcId")


def create_subnet_if_needed(vpc_id):
    subnet = describe_subnet()

    if not subnet:
        network_cidr = z0.service.lookup("aws-network-cidr")

        logger.info("creating subnet")
        create_subnet = client.create_subnet(CidrBlock=network_cidr, VpcId=vpc_id)
        subnet_id = create_subnet.get("Subnet").get("SubnetId")
        create_tags(subnet_id)

        return subnet_id
    else:
        return subnet.get("SubnetId")


def create_internet_gateway_if_needed(vpc_id):
    internet_gateway = describe_internet_gateway()

    if not internet_gateway:
        logger.info("creating internet gateway")
        internet_gateway_id = client.create_internet_gateway().get("InternetGateway").get("InternetGatewayId")
        create_tags(internet_gateway_id)

        logger.info("attaching internet gateway to vpc")
        client.attach_internet_gateway(InternetGatewayId=internet_gateway_id, VpcId=vpc_id)

        logger.info("checking route table")
        route_tables = client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("RouteTables")

        logger.info("adding outbound route")
        client.create_route(DestinationCidrBlock="0.0.0.0/0", GatewayId=internet_gateway_id, RouteTableId=route_tables[0].get("RouteTableId"))


def lookup_latest_image():
    ami_criteria = z0.service.lookup("aws-ami-criteria")

    logger.info("checking latest image")
    response = client.describe_images(**json.loads(ami_criteria))
    images = response.get("Images")
    images.sort(key=lambda image: image.get("CreationDate"), reverse=True)

    return images[0]


def create_instance_if_needed(subnet_id):
    instance = describe_instance()

    if not instance:
        image = lookup_latest_image()
        instance_type = z0.service.lookup("aws-instance-type")
        user_data = z0.service.lookup("aws-user-data")

        logger.info("creating instance")
        run_instances = client.run_instances(
            ImageId=image.get("ImageId"),
            MinCount=1,
            MaxCount=1,
            KeyName="keypair",  # TODO
            InstanceType=instance_type,
            BlockDeviceMappings=[{
                "DeviceName": image.get("RootDeviceName"),
                "Ebs": {"VolumeSize": int(z0.service.lookup("aws-volume-size"))}
            }],
            SubnetId=subnet_id,
            UserData=jinja2.Template(user_data).render(url=z0.service.url, project=z0.service.project, stage=z0.service.stage)
        )
        instance_id = run_instances.get("Instances")[0].get("InstanceId")
        client.get_waiter("instance_running").wait(InstanceIds=[instance_id])
        create_tags(instance_id)

        return instance_id
    else:
        return instance.get("InstanceId")


def create_address_if_needed(instance_id):
    address = describe_address()

    if not address:
        logger.info("creating address")
        allocate_address = client.allocate_address()
        allocation_id = allocate_address.get("AllocationId")
        create_tags(allocation_id)

        logger.info("associating address with instance")
        client.associate_address(AllocationId=allocation_id, InstanceId=instance_id)

        return allocate_address.get("PublicIp")
    else:
        return address.get("PublicIp")


def destroy_address_if_needed():
    address = describe_address()
    if address:
        logger.info("disassociating address from instance")
        client.disassociate_address(AssociationId=address.get("AssociationId"))

        logger.info("destroying address")
        client.release_address(AllocationId=address.get("AllocationId"))


def destroy_instance_if_needed():
    instance = describe_instance()
    if instance:
        logger.info("destroying instance")
        instance_ids = {"InstanceIds": [instance.get("InstanceId")]}
        client.terminate_instances(**instance_ids)
        client.get_waiter("instance_terminated").wait(**instance_ids)


def destroy_internet_gateway_if_needed():
    internet_gateway = describe_internet_gateway()
    if internet_gateway:
        internet_gateway_id = internet_gateway.get("InternetGatewayId")

        logger.info("detaching internet gateway from vpc")
        client.detach_internet_gateway(
            InternetGatewayId=internet_gateway_id,
            VpcId=internet_gateway.get("Attachments")[0].get("VpcId")
        )

        logger.info("destroying internet gateway")
        client.delete_internet_gateway(InternetGatewayId=internet_gateway_id)


def destroy_subnet_if_needed():
    subnet = describe_subnet()
    if subnet:
        logger.info("destroying subnet")
        client.delete_subnet(SubnetId=subnet.get("SubnetId"))


def destroy_vpc_if_needed():
    vpc = describe_vpc()
    if vpc:
        logger.info("destroying vpc")
        client.delete_vpc(VpcId=vpc.get("VpcId"))
