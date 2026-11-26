# Kubernetes Services

## Stable access to pods
A Service gives a set of pods a stable virtual IP and DNS name, because pod IP addresses change. The Service selects pods using label selectors, and traffic is spread across the ready pods that match.

## Service types
ClusterIP is the default and is reachable only inside the cluster. NodePort opens the same port on every node. LoadBalancer asks the cloud provider to provision an external load balancer. ExternalName maps the Service to a DNS name outside the cluster and involves no proxying.

## Endpoints and readiness
Only pods that pass their readiness check are included in the Service endpoints. A pod that is not ready receives no traffic, which is what makes rolling updates safe for clients.
