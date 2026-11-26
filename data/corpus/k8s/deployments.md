# Kubernetes Deployments

## Purpose
A Deployment declares the desired state for a set of identical pods and manages them through ReplicaSets. Changing the pod template creates a new ReplicaSet and the Deployment controller gradually shifts replicas from the old one to the new one.

## Rolling updates
The default strategy is RollingUpdate. Two settings control its pace: maxSurge is how many extra pods may exist above the desired count during the update, and maxUnavailable is how many pods may be missing. Setting maxUnavailable to zero keeps full capacity during a rollout, provided new pods become ready before old ones are removed.

## Rollbacks
Deployments keep a history of old ReplicaSets, limited by revisionHistoryLimit, which defaults to ten. The command kubectl rollout undo returns to the previous revision, and kubectl rollout status shows progress. The Recreate strategy instead stops all old pods before starting new ones, causing downtime.
