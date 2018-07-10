import configparser
import logging
import subprocess
import sys

import jinja2
import requests

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter("{asctime} | {levelname:<7.7} | {name:<25.25} | {message}", style="{"))
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(stream_handler)

default_filename = "zebr0-aws.conf"
default_path = "/etc/" + default_filename

parser = configparser.ConfigParser()
parser.read([default_path, default_filename])

base_url = parser.get("config", "base_url", fallback="https://raw.githubusercontent.com/zebr0/zebr0-aws-config/master")


def edit_config(filename):
    parser["config"] = {
        "base_url": base_url
    }

    with open(filename, "w") as file:
        parser.write(file)
    subprocess.call(["/usr/bin/editor", filename])


class Service:
    def __init__(self, project, stage, debug):
        self.project = project
        self.stage = stage

        self.logger = logging.getLogger("zebr0-aws.config.service")
        self.cache = {}

        if debug:
            root_logger.setLevel(logging.DEBUG)
        self.logger.info("base_url: %s", base_url)
        self.logger.info("project: %s", project)
        self.logger.info("stage: %s", stage)

    def lookup(self, key):
        if not self.cache.get(key):
            self.cache[key] = self.remote_lookup(key)
        return self.cache.get(key)

    def remote_lookup(self, key):
        self.logger.info("looking for key '%s' in remote repository", key)
        for path in [[base_url, self.project, self.stage, key],
                     [base_url, self.project, key],
                     [base_url, key]]:
            response = requests.get("/".join(path))
            if response.ok:
                return jinja2.Template(response.text.strip()).render(project=self.project, stage=self.stage)
        raise LookupError("key '{}' not found anywhere for project '{}', stage '{}' in '{}'".format(key, self.project, self.stage, base_url))
