import configparser
import subprocess

import requests

default_filename = "zebr0-aws.conf"
default_path = "/etc/" + default_filename

parser = configparser.ConfigParser()
parser.read([default_path, default_filename])

base_url = parser.get("config", "base_url", fallback="https://raw.githubusercontent.com/zebr0/zebr0-files/master")


def fetch_distribution(project):
    return fetch(project, "distribution",
                 default='{"Filters": [{"Name": "name", "Values": ["ubuntu/images/hvm-ssd/ubuntu-bionic-*"]}], "Owners": ["099720109477"]}')


def fetch_instance_type(project, stage):
    return fetch(project, stage, "instance-type", default="t2.micro")


def fetch_network_cidr(project, stage):
    return fetch(project, stage, "network-cidr", default="192.168.0.0/24")


def fetch(*args, default=None):
    key = "/".join(args)
    response = requests.get(base_url + "/" + key)
    if response.ok:
        return response.text.strip()
    elif default:
        print("missing configuration key: '{}', using default value: '{}'".format(key, default))
        return default


def edit_config(filename):
    parser["config"] = {
        "base_url": base_url
    }

    with open(filename, "w") as file:
        parser.write(file)
    subprocess.call(["/usr/bin/editor", filename])
