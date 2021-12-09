# Following code was written by Andrew Block
# Title: build_schema.py
# Author: Andrew Block
# Date: 2021
# Availability: https://github.com/sabre1041/k8s-manifest-validation/blob/main/scripts/build_schema.py

from shutil import which
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import argparse
import os
import urllib
import sys
import urllib
import ssl
import yaml
import json
import subprocess

existing_definitions_file = None

OPENSHIFT_API_SPEC_FILE = "openshift-api-spec.json"

script_dir = os.path.dirname(os.path.realpath(__file__))

openapi2jsonschema_location = which("openapi2jsonschema")


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


# Check if prerequisite executables are available
if openapi2jsonschema_location is None:
    print("Error: openapi2jsonschema is not available")
    sys.exit(1)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

parser = argparse.ArgumentParser()

parser.add_argument("-u", "--url", action="store", dest="url",
                    required=True, help="OpenShift API URL")
parser.add_argument("-t", "--token", action="store",
                    dest="token", required=True, help="OpenShift API Token")
parser.add_argument("-ov", "--openshift-version", action="store",
                    dest="openshift_version", default="master", help="OpenShift Version")
parser.add_argument("-d", "--destination", action="store",
                    dest="destination", help="Output file")
parser.add_argument("-s", "--strict", action="store",
                    dest="strict", help="Strict schema")
parser.add_argument("--dry-run", action="store", type=str2bool, nargs='?',
                    const=True, default=False, dest="dryrun", help="Strict schema")

args = parser.parse_args()


def loadYAML(location):
    if os.path.isfile(location):
        req = urllib.request.Request(
            "file://" + os.path.realpath(location))
        res = urllib.request.urlopen(req)
        return yaml.load(
            res.read(), Loader=yaml.SafeLoader)
    else:
        headers = {"Authorization": "Bearer {}".format(args.token)}

        req = urllib.request.Request(url=openapi_endpoint, headers=headers)

        try:
            res = urllib.request.urlopen(req, context=ctx)
            return yaml.load(res.read(), Loader=yaml.SafeLoader)
        except HTTPError as e:
            print('The server couldn\'t fulfill the request.')
            print('Error code: ', e.code)
            sys.exit(1)
        except URLError as e:
            print('Failed to reach a server.')
            print('Reason: ', e.reason)
            sys.exit(1)


openapi_endpoint = "{}/openapi/v2".format(args.url)

print("Downloading and parsing API schema from: {}\n".format(openapi_endpoint))

openapi_data = loadYAML(openapi_endpoint)

definitions = openapi_data["definitions"]
spec_file = os.path.join(script_dir, OPENSHIFT_API_SPEC_FILE)
delete_list = []
invalid_specs_groups = []
valid_specs_groups = []
invalid_specs_kinds = []
valid_specs_kinds = []
invalid_kinds_fp = os.path.join(script_dir,  "skip_kinds")


with open(spec_file, "w") as openapi_spec_file:
    for type_name in definitions:
        type_def = definitions[type_name]
        if "x-kubernetes-group-version-kind" in type_def:
            for kube_ext in type_def["x-kubernetes-group-version-kind"]:
                if "properties" not in type_def:
                    invalid_specs_groups.append(type_def["x-kubernetes-group-version-kind"][0]["group"])
                    invalid_specs_kinds.append(type_def["x-kubernetes-group-version-kind"][0]["kind"])
                    delete_list.append(type_name)
                else:
                    valid_specs_groups.append(type_def["x-kubernetes-group-version-kind"][0]["group"])
                    valid_specs_kinds.append(type_def["x-kubernetes-group-version-kind"][0]["kind"])

    try:
        with open(invalid_kinds_fp, "r+") as skf:
            skip_kinds_file = skf.read()
            skip_kinds_file = skip_kinds_file.rstrip('\n')
            skip_kinds_file = skip_kinds_file.split(",")
    except IOError:
        skip_kinds_file = []

   # Iterate through invalid kinds and add them to file if they do not clash with other CRDs
    with open(invalid_kinds_fp, "w+") as skf:
        for item in skip_kinds_file:
            if item == "":
                skip_kinds_file.remove(item)
            if item in valid_specs_kinds:
                skip_kinds_file.remove(item)
        for index, item in enumerate(invalid_specs_kinds):
            print(valid_specs_groups)
            if (item not in skip_kinds_file):
                if item in valid_specs_kinds:
                    idx = valid_specs_kinds.index(item)
                    if invalid_specs_groups[index] != valid_specs_groups[idx]:
                        skip_kinds_file.append(item)
                else:
                    skip_kinds_file.append(item)

        print("Following kinds are added to the file:")
        print(skip_kinds_file)
        skf.write (",".join(skip_kinds_file))

    if len(delete_list) > 0:
        print("The following API resources do not have valid OpenAPI specifications:\n")

    for del_item in delete_list:
        print(del_item)
        del definitions[del_item]
    openapi_spec_file.write(json.dumps(openapi_data, indent=2))

if args.dryrun:
    print("\nDry run activated: Not building schema\n")
    sys.exit(0)

destination = args.destination

if destination is None:
    destination = "{}/openshift-json-schema".format(script_dir)

output_destination = os.path.join(
    destination, "{}-standalone".format(args.openshift_version))

if args.strict is not None:
    output_destination += "-strict"


# Check if existing _definitions.json file exists
definitions_file = os.path.join(output_destination, "_definitions.json")
if os.path.isfile(definitions_file):
    print("\nParsing existing _definitions.json file\n")
    existing_definitions_file = loadYAML(definitions_file)


command = [openapi2jsonschema_location, "-o",
           output_destination, "--expanded", "--kubernetes", spec_file]

if args.strict is not None:
    command.append("--strict")


print("\nProcessing schemas into {}\n".format(output_destination))

job = subprocess.Popen(
    command,
    shell=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    close_fds=True,
)

try:
    (stdout, stderr) = job.communicate(timeout=300)
except subprocess.TimeoutExpired:
    job.kill()
    (stdout, stderr) = job.communicate()
stdout = stdout.decode("utf-8")
stderr = stderr.decode("utf-8")
print("[STDERR]: %s" % stderr)
print("[STDOUT]: %s" % stdout)

# Attempt to Merge _definitions file
if existing_definitions_file is not None:
    print("Merging Contents from Existing Definition File")
    new_definitions_file = loadYAML(definitions_file)

    with open(definitions_file, "w") as updated_definitions_file:
        existing_definitions_file.update(new_definitions_file)
        updated_definitions_file.write(
            json.dumps(existing_definitions_file, indent=2))


if os.path.exists(spec_file):
    os.remove(spec_file)
