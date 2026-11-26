# Kubernetes Probes

## Liveness probes
A liveness probe checks whether a container is still healthy. If it fails repeatedly, the kubelet restarts the container. Use it to recover from deadlocks, not to check dependencies.

## Readiness probes
A readiness probe decides whether a pod should receive traffic. When it fails, the pod is removed from Service endpoints but the container is not restarted.

## Startup probes
A startup probe is meant for applications that take a long time to boot. While it has not yet succeeded, liveness and readiness probes are disabled, so a slow start is not mistaken for a failure. Once it succeeds the other probes take over. Probe handlers can be HTTP GET, TCP socket, exec commands or gRPC.
