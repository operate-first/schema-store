# Operate First - OpenShift JSON schemas

This repository stores OpenShift JSON schemas used with Kubeval tool to validate YAML Kubernetes configuration files.

## Structure of the repository

Schemas are stored as JSON files in schemas/ at the root of the repo. The directories within schemas are named using the following format: `${version}-${reference}-${mode}`, where:

```
version = Version of Kubernetes from which schemas were extracted (default for Kubeval is "master").
reference = Refence tells us if JSON schemas contain all the definitions of parameters, or the definitions are referenced in a different file and schema contains only reference to this file.
mode = Mode tells if we are using stronger strict JSON schemas which do not allow arbitrary parameters or weaker JSON schemas which allow arbitrary parameters.
```

## Acquiring schemas
To acquire JSON schemas we can use OpenAPi endpoint of cluster and tool called [openapi2jsonschema](https://github.com/instrumenta/openapi2jsonschema) which generates schemas from given OpenAPI JSON.
Acquiring schemas from big cluster may prove challenging. OpenAPI may not have all CRDs defined. This will lead to openapi2jsonschema failing. To resolve this problem we can use script which  Andrew Block [created](https://github.com/sabre1041/k8s-manifest-validation/blob/main/scripts/build_schema.py). Details on how to use it and in depth reasons why we have to use it can be found in this [blog](https://cloud.redhat.com/blog/validating-openshift-manifests-in-a-gitops-world).
Script mentioned above is included in this repository. Use it running following command when you are logged in to your cluster through CLI:

```
python build_schema.py -u $(oc whoami --show-server) -t $(oc whoami -t) -s STRICT
```
When the script finishes there will be new folders called `openshift-json-schema/master-standalone-strict` containing all the schemas obtained from OpenAPI endpoint. After that copy missing schema to repository.
This script also creates (or appends) a file with kinds which do not have valid schemas. This file is called `skip_kinds` and is used in the kubeval validation.
