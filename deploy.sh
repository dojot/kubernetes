#!/bin/bash

# Check if parameters are set
if [ $# -lt 2 ]; then
    echo "Error: The external ip parameter and the ceph.conf file is required\n"
    echo "./deploy.sh AA.BB.CC.DD CEPH_CONF_FILE [TAG]"
    exit
fi

# Read the external ip
EXTERNAL_IP=$1

# Get the mon list from the ceph.conf file
CEPH_MON_IPS=$(grep mon_host ${2} | egrep -o "[0-9\.\,]+" | sed -r "s/[0-9\.]+/'\0:6789'/g")

# Read the tag value, if not set, use the default value "latest"
TAG=${3:-latest}

# Update the external ip on the yaml files
sed -i "s/\[EXTERNAL_IP\]/${EXTERNAL_IP}/g" manifests/apigw.yaml
sed -i -r "s/(dojot\/[a-zA-Z\-]+).*/\1:${TAG}/g" manifests/*.yaml
sed -i "s/\[CEPH_MONITORS\]/\[${CEPH_MON_IPS}\]/g" manifests/*.yaml

# Create the dojot namespace
kubectl create namespace dojot

# Create the volume images on Ceph
rbd create postgres-volume --size 50G
rbd create mongo-volume --size 250G

# Disable some features not available on Ubuntu 16.04 Kernel
rbd feature disable postgres-volume exclusive-lock, object-map, fast-diff, deep-flatten
rbd feature disable mongo-volume exclusive-lock, object-map, fast-diff, deep-flatten

# Create configuration files mappings
kubectl create -n dojot configmap pdp-ws-jboss-config --from-file=pdp-ws/
kubectl create -n dojot configmap iotagent-conf --from-file=iotagent/config.js

# Deploy Dojot services
kubectl create -n dojot -f manifests/apigw.yaml
kubectl create -n dojot -f manifests/auth.yaml
kubectl create -n dojot -f manifests/coap.yaml
kubectl create -n dojot -f manifests/device-manager.yaml
kubectl create -n dojot -f manifests/gui.yaml
kubectl create -n dojot -f manifests/iotagent.yaml
kubectl create -n dojot -f manifests/mashup.yaml
kubectl create -n dojot -f manifests/mongo.yaml
kubectl create -n dojot -f manifests/mqtt.yaml
kubectl create -n dojot -f manifests/orion.yaml
kubectl create -n dojot -f manifests/perseo-core.yaml
kubectl create -n dojot -f manifests/perseo-fe.yaml
kubectl create -n dojot -f manifests/postgres.yaml
kubectl create -n dojot -f manifests/sth.yaml

kubectl create -n dojot configmap kong-route-config --from-file=config_scripts/kong.config.sh
kubectl create -n dojot configmap create-admin-user --from-file=config_scripts/create-admin-user.sh

kubectl create -n dojot -f manifests/config-jobs.yaml

# Changes the external ip back to a tag
sed -i "s/${EXTERNAL_IP}/\[EXTERNAL_IP\]/g" manifests/apigw.yaml
