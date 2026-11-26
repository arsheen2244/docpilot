# Kubernetes Pods

## What a pod is
A pod is the smallest deployable unit in Kubernetes. It wraps one or more containers that are scheduled together onto the same node. Containers in a pod share a network namespace, so they reach each other over localhost and share one IP address.

## Storage and lifecycle
Containers in a pod can mount the same volumes to share files. Pods are ephemeral: when a pod is deleted or its node fails, it is not resurrected, and a controller must create a replacement with a new IP address. For that reason applications should not rely on a pod's IP address staying the same.

## Multi-container patterns
Sidecar containers extend the main container, for example by shipping logs or proxying traffic. Init containers run to completion before the app containers start, which makes them useful for setup work such as waiting for a database or fetching configuration.
