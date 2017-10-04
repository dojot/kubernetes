#!/bin/sh

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
kubectl create -n dojot -f manifests/pdp.yaml
kubectl create -n dojot -f manifests/perseo-core.yaml
kubectl create -n dojot -f manifests/perseo-fe.yaml
kubectl create -n dojot -f manifests/postgres.yaml
kubectl create -n dojot -f manifests/sth.yaml
