#!/bin/bash

# Check if parameters are set
if [ $# -lt 1 ]; then
    echo "Error: The external ip parameter is required\n"
    echo "./deploy.sh AA.BB.CC.DD"
    exit
fi

# Read the external ip
EXTERNAL_IP=$1

# One-time update the external ip on the yaml files
sed -i "s/\[EXTERNAL_IP\]/${EXTERNAL_IP}/g" manifests/apigw.yaml

# Create the dojot namespace
kubectl create namespace dojot

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
