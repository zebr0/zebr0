import json
import logging

import boto3


class Service:
    def __init__(self, config_service):
        self.config_service = config_service

        self.logger = logging.getLogger("zebr0-aws.ec2.service")

        region = self.config_service.lookup("aws-region")
        self.logger.info("creating ec2 client")
        self.client = boto3.client(service_name="ec2", region_name=region)

        self.default_filters = [{"Name": "tag:project", "Values": [self.config_service.project]},
                                {"Name": "tag:stage", "Values": [self.config_service.stage]}]

    def describe_vpc(self):
        self.logger.info("checking vpc")
        vpcs = self.client.describe_vpcs(Filters=self.default_filters).get("Vpcs")
        return vpcs[0] if vpcs else None

    def describe_subnet(self):
        self.logger.info("checking subnet")
        subnets = self.client.describe_subnets(Filters=self.default_filters).get("Subnets")
        return subnets[0] if subnets else None

    def describe_instance(self):
        self.logger.info("checking instance")
        filters = self.default_filters + [{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
        reservations = self.client.describe_instances(Filters=filters).get("Reservations")
        return reservations[0].get("Instances")[0] if reservations else None

    def describe_internet_gateway(self):
        self.logger.info("checking internet gateway")
        internet_gateways = self.client.describe_internet_gateways(Filters=self.default_filters).get("InternetGateways")
        return internet_gateways[0] if internet_gateways else None

    def describe_address(self):
        self.logger.info("checking address")
        addresses = self.client.describe_addresses(Filters=self.default_filters).get("Addresses")
        return addresses[0] if addresses else None

    def create_tags(self, resource_id):
        self.logger.info("updating resource tags")
        self.client.create_tags(Resources=[resource_id], Tags=[{"Key": "project", "Value": self.config_service.project},
                                                               {"Key": "stage", "Value": self.config_service.stage}])

    def create_vpc_if_needed(self):
        vpc = self.describe_vpc()

        if not vpc:
            network_cidr = self.config_service.lookup("vm-network-cidr")

            self.logger.info("creating vpc")
            create_vpc = self.client.create_vpc(CidrBlock=network_cidr)
            vpc_id = create_vpc.get("Vpc").get("VpcId")
            self.client.get_waiter("vpc_exists").wait(VpcIds=[vpc_id])
            self.create_tags(vpc_id)

            self.logger.info("checking security group")
            security_groups = self.client.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("SecurityGroups")

            self.logger.info("adding ingress permissions")
            self.client.authorize_security_group_ingress(
                GroupId=security_groups[0].get("GroupId"),
                IpPermissions=[
                    {"FromPort": 80, "ToPort": 80, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                    {"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                    {"FromPort": -1, "ToPort": -1, "IpProtocol": "icmp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                    {"FromPort": 22, "ToPort": 22, "IpProtocol": "tcp", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}  # TODO
                ]
            )

            return vpc_id
        else:
            return vpc.get("VpcId")

    def create_subnet_if_needed(self, vpc_id):
        subnet = self.describe_subnet()

        if not subnet:
            network_cidr = self.config_service.lookup("vm-network-cidr")

            self.logger.info("creating subnet")
            create_subnet = self.client.create_subnet(CidrBlock=network_cidr, VpcId=vpc_id)
            subnet_id = create_subnet.get("Subnet").get("SubnetId")
            self.create_tags(subnet_id)

            return subnet_id
        else:
            return subnet.get("SubnetId")

    def create_internet_gateway_if_needed(self, vpc_id):
        internet_gateway = self.describe_internet_gateway()

        if not internet_gateway:
            self.logger.info("creating internet gateway")
            internet_gateway_id = self.client.create_internet_gateway().get("InternetGateway").get("InternetGatewayId")
            self.create_tags(internet_gateway_id)

            self.logger.info("attaching internet gateway to vpc")
            self.client.attach_internet_gateway(InternetGatewayId=internet_gateway_id, VpcId=vpc_id)

            self.logger.info("checking route table")
            route_tables = self.client.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("RouteTables")

            self.logger.info("adding outbound route")
            self.client.create_route(DestinationCidrBlock="0.0.0.0/0", GatewayId=internet_gateway_id, RouteTableId=route_tables[0].get("RouteTableId"))

    def lookup_latest_image_id(self):
        image = self.config_service.lookup("aws-ami-criteria")

        self.logger.info("checking latest image")
        response = self.client.describe_images(**json.loads(image))
        images = response.get("Images")
        images.sort(key=lambda image: image.get("CreationDate"), reverse=True)
        latest = images[0]

        return latest.get("ImageId")

    def create_instance_if_needed(self, subnet_id):
        instance = self.describe_instance()

        if not instance:
            image_id = self.lookup_latest_image_id()
            instance_type = self.config_service.lookup("aws-instance-type")
            user_data = self.config_service.lookup("vm-user-data")

            self.logger.info("creating instance")
            run_instances = self.client.run_instances(
                ImageId=image_id,
                MinCount=1,
                MaxCount=1,
                KeyName="keypair",  # TODO
                InstanceType=instance_type,
                SubnetId=subnet_id,
                UserData=user_data
            )
            instance_id = run_instances.get("Instances")[0].get("InstanceId")
            self.client.get_waiter("instance_running").wait(InstanceIds=[instance_id])
            self.create_tags(instance_id)

            return instance_id
        else:
            return instance.get("InstanceId")

    def create_address_if_needed(self, instance_id):
        address = self.describe_address()

        if not address:
            self.logger.info("creating address")
            allocate_address = self.client.allocate_address()
            allocation_id = allocate_address.get("AllocationId")
            self.create_tags(allocation_id)

            self.logger.info("associating address with instance")
            self.client.associate_address(AllocationId=allocation_id, InstanceId=instance_id)

            return allocate_address.get("PublicIp")
        else:
            return address.get("PublicIp")

    def destroy_address_if_needed(self):
        address = self.describe_address()
        if address:
            self.logger.info("disassociating address from instance")
            self.client.disassociate_address(AssociationId=address.get("AssociationId"))

            self.logger.info("destroying address")
            self.client.release_address(AllocationId=address.get("AllocationId"))

    def destroy_instance_if_needed(self):
        instance = self.describe_instance()
        if instance:
            self.logger.info("destroying instance")
            instance_ids = {"InstanceIds": [instance.get("InstanceId")]}
            self.client.terminate_instances(**instance_ids)
            self.client.get_waiter("instance_terminated").wait(**instance_ids)

    def destroy_internet_gateway_if_needed(self):
        internet_gateway = self.describe_internet_gateway()
        if internet_gateway:
            internet_gateway_id = internet_gateway.get("InternetGatewayId")

            self.logger.info("detaching internet gateway from vpc")
            self.client.detach_internet_gateway(
                InternetGatewayId=internet_gateway_id,
                VpcId=internet_gateway.get("Attachments")[0].get("VpcId")
            )

            self.logger.info("destroying internet gateway")
            self.client.delete_internet_gateway(InternetGatewayId=internet_gateway_id)

    def destroy_subnet_if_needed(self):
        subnet = self.describe_subnet()
        if subnet:
            self.logger.info("destroying subnet")
            self.client.delete_subnet(SubnetId=subnet.get("SubnetId"))

    def destroy_vpc_if_needed(self):
        vpc = self.describe_vpc()
        if vpc:
            self.logger.info("destroying vpc")
            self.client.delete_vpc(VpcId=vpc.get("VpcId"))
