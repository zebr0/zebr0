import configparser
import subprocess

import requests

parser = configparser.ConfigParser()
parser.read(["/etc/zebr0.conf", "zebr0.conf"])

base_url = parser.get("config", "base_url", fallback="https://raw.githubusercontent.com/zebr0/zebr0-files/master")


def fetch_distribution(project):
    return _fetch(project, "distribution", default="ubuntu-bionic")


def fetch_instance_type(project, stage):
    return _fetch(project, stage, "instance-type", default="t2.micro")


def fetch_network_cidr(project, stage):
    return _fetch(project, stage, "network-cidr", default="192.168.0.0/24")


def fetch_domain_name():
    return _fetch("domain-name", default=None)


def _fetch(*args, default):
    key = "/".join(args)
    response = requests.get(base_url + "/" + key)
    if response.ok:
        return response.text.strip()
    else:
        print("missing key:", key)
        return default


def edit_config(filename):
    parser["config"] = {
        "base_url": base_url
    }

    with open(filename, "w") as file:
        parser.write(file)
    subprocess.call(["/usr/bin/editor", filename])
