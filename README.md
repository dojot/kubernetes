# dojot Kubernetes Manifests

---

This repository contains the necessary manifests and configuration files 
for a quick deployment of the dojot platform into a kubernetes cluster.

---

## Kubernetes

Kubernetes or "K8s" is an open-source system for automating deployment,
scaling and management of containerized applications that was originally
designed by Google and donated to the Cloud Native Computing Foundation.
It aims to provide a "platform for automating deployment, scaling, and 
operations of application containers across clusters of hosts". 
It supports a range of container tools, including Docker.

## Manifests

The manifests contained on this repository compose the model of a basic
scenario of dojot deployment where most components are deployed as single
instances.

This manifests comprise the entirety of containers that are required to run
dojot, including third-party infrastructure components like Postgres and Zookeeper.

Most components are divided in two manifests, one that defines the deployment
of the container and another that defines the service to access it.

The third-party databases that are deployed here are PostgreSQL, Redis and MongoDB.
All this databases are deployed as Clusters with replicas for High-Availability and
have their storage persisted. 
At the moment, cluster size must be changed manually on the manifests.

## How to use it

A guide on how to use this repository to deploy to Kubernetes can be found at the
[read the Docs documentation for dojot.](http://dojotdocs.readthedocs.io/en/latest/install/kube_guide.html)

### Disclaimer

This deployment option is best suited to development and functional environments.
It is not production-ready and requires improvements for real world deployments.
 