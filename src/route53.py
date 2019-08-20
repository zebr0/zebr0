import logging

import boto3

import z0

logger = logging.getLogger("zebr0-aws.route53")
resource_record_set = None

try:
    region = z0.service.lookup("aws-region")
    logger.info("creating route53 client")
    client = boto3.client(service_name="route53", region_name=region)

    domain_name = z0.service.lookup("domain-name") + "."

    logger.info("checking hosted zone")
    hosted_zones = client.list_hosted_zones_by_name(DNSName=domain_name, MaxItems="1").get("HostedZones")
    if hosted_zones and hosted_zones[0].get("Name") == domain_name:
        hosted_zone_id = hosted_zones[0].get("Id")
        fqdn = z0.service.lookup("fqdn") + "."

        logger.info("checking resource record set")
        resource_record_sets = client.list_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            StartRecordName=fqdn,
            StartRecordType="A",
            MaxItems="1"
        ).get("ResourceRecordSets")
        if resource_record_sets and resource_record_sets[0].get("Name") == fqdn:
            resource_record_set = resource_record_sets[0]
    else:
        logger.warning("no hosted zone was found in route53 for the '%s' domain, it needs to be created manually", domain_name)
except LookupError as error:
    logger.warning("%s, skipping dns entry management", error)


def create_dns_entry_if_needed(address):
    if not resource_record_set:
        ttl = int(z0.service.lookup("dns-record-ttl"))

        logger.info("creating resource record set")
        client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={"Changes": [{
                "Action": "CREATE",
                "ResourceRecordSet": {
                    "Name": fqdn,
                    "Type": "A",
                    "TTL": ttl,
                    "ResourceRecords": [{"Value": address}]
                }
            }]}
        )


def destroy_dns_entry_if_needed():
    if resource_record_set:
        logger.info("destroying resource record set")
        client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={"Changes": [{
                "Action": "DELETE",
                "ResourceRecordSet": resource_record_set
            }]}
        )
