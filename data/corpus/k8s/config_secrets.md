# ConfigMaps and Secrets

## ConfigMaps
A ConfigMap stores non-confidential configuration as key-value pairs. Pods can consume it as environment variables, command-line arguments or files in a mounted volume. Values from a mounted ConfigMap volume are updated eventually when the ConfigMap changes, but environment variables are only read at container start.

## Secrets
A Secret holds sensitive data such as passwords and tokens. By default values are only base64 encoded, which is not encryption, and they are stored unencrypted in etcd unless encryption at rest is configured. Access should be restricted with RBAC. Secrets can also be mounted as files or exposed as environment variables.

## Size limit
Both objects are limited to 1 MiB in size.
