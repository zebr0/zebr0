import logging

import boto3

import z0

logger = logging.getLogger("zebr0-aws.route53")
logger.info("creating route53 client")
client = boto3.client(service_name="route53", region_name=z0.service.lookup("aws-region"))

domain_name = z0.service.lookup("domain-name") + "."
fqdn = z0.service.lookup("fqdn") + "."


def get_hosted_zone_id():
    logger.info("checking hosted zone")
    hosted_zones = client.list_hosted_zones_by_name(DNSName=domain_name, MaxItems="1").get("HostedZones")
    if hosted_zones and hosted_zones[0].get("Name") == domain_name:
        return hosted_zones[0].get("Id")
    else:
        logger.warning("no hosted zone was found in route53 for the '%s' domain (it needs to be created manually), skipping dns entry management", domain_name)


def get_resource_record_set(hosted_zone_id):
    logger.info("checking resource record set")
    resource_record_sets = client.list_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        StartRecordName=fqdn,
        StartRecordType="A",
        MaxItems="1"
    ).get("ResourceRecordSets")
    return resource_record_sets[0] if resource_record_sets and resource_record_sets[0].get("Name") == fqdn else None


def create_dns_entry_if_needed(address):
    hosted_zone_id = get_hosted_zone_id()
    if hosted_zone_id and not get_resource_record_set(hosted_zone_id):
        logger.info("creating resource record set")
        client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={"Changes": [{
                "Action": "CREATE",
                "ResourceRecordSet": {
                    "Name": fqdn,
                    "Type": "A",
                    "TTL": int(z0.service.lookup("dns-record-ttl")),
                    "ResourceRecords": [{"Value": address}]
                }
            }]}
        )


def destroy_dns_entry_if_needed():
    hosted_zone_id = get_hosted_zone_id()
    if hosted_zone_id:
        resource_record_set = get_resource_record_set(hosted_zone_id)
        if resource_record_set:
            logger.info("destroying resource record set")
            client.change_resource_record_sets(
                HostedZoneId=hosted_zone_id,
                ChangeBatch={"Changes": [{
                    "Action": "DELETE",
                    "ResourceRecordSet": resource_record_set
                }]}
            )
