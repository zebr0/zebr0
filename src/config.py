import configparser
import subprocess

import requests

default_filename = "zebr0-aws.conf"
default_path = "/etc/" + default_filename

parser = configparser.ConfigParser()
parser.read([default_path, default_filename])

base_url = parser.get("config", "base_url", fallback="https://raw.githubusercontent.com/zebr0/zebr0-aws-config/master")


def lookup(project, stage, key):
    for path in [[base_url, project, stage, key],
                 [base_url, project, key],
                 [base_url, key]]:
        response = requests.get("/".join(path))
        if response.ok:
            return response.text.strip()
    raise LookupError("key '{}' not found anywhere for project '{}', stage '{}' in '{}'".format(key, project, stage, base_url))


def edit_config(filename):
    parser["config"] = {
        "base_url": base_url
    }

    with open(filename, "w") as file:
        parser.write(file)
    subprocess.call(["/usr/bin/editor", filename])
