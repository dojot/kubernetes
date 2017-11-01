#!/bin/bash

function print_error {
    echo "Error: The deployment destination must be configured"
    echo " Use LOCAL for a local environment or GCP to start the google cloud deployment service"
    echo
    echo "   For local environments the parameters required are an external IP, the Ceph configuration file and optionally the version Tag "
    echo "    $ ./deploy.sh LOCAL EXTERNAL_IP CEPH_CONF_FILE [TAG]"
    echo
    echo "   For Google Cloud deployments there is only an optional version Tag parameter"
    echo "    $ ./deploy.sh GCP [TAG]"
    exit
}

# Check if parameters are set
if [ $# -lt 1 ]; then
    print_error
fi

DEPLOY_TYPE=$1

if [ ${DEPLOY_TYPE} = "LOCAL" ]; then
    if [ $# -lt 3 ]; then
        print_error
    fi

    # Read the external ip
    EXTERNAL_IP=$2
    # Get the mon list from the ceph.conf file
    CEPH_MON_IPS=$(grep mon_host ${3} | egrep -o "[0-9\.\,]+" | sed -r "s/[0-9\.]+/\0:6789/g")
    # Read the tag value, if not set, use the default value "latest"
    TAG=${4:-latest}

    # Update the external ip on the yaml files
    sed -i "s/\[EXTERNAL_IP\]/${EXTERNAL_IP}/g" manifests/LOCAL/external-access.yaml
    # Update the tag of the containers
    sed -i -r "s/(dojot\/[a-zA-Z\-]+).*/\1:${TAG}/g" manifests/*.yaml
    # Update the ceph monitor adresses for the volumes
    sed -i -r "s/\[CEPH_MONITORS\]/${CEPH_MON_IPS}/g" manifests/LOCAL/*.yaml

    # Create the dojot namespace
    kubectl create namespace dojot

    # Create configuration files mappings
    kubectl create -n dojot configmap iotagent-conf --from-file=iotagent/config.js
    kubectl create -n dojot configmap kong-route-config --from-file=config_scripts/kong.config.sh
    kubectl create -n dojot configmap create-admin-user --from-file=config_scripts/create-admin-user.sh

    # Deploy Dojot services
    kubectl create -n dojot -f manifests/LOCAL/ceph-secret-user.yaml
    kubectl create -n kube-system -f manifests/LOCAL/ceph-secret-admin.yaml
    kubectl create -f manifests/LOCAL/standard-storage-class.yaml
    kubectl create -f manifests/LOCAL/rbd-provisioner.yaml
    kubectl create -n dojot -f manifests/LOCAL/external-access.yaml
    kubectl create -n dojot -f manifests/

    # Wait for redis cluster to be bootstrapped
    until kubectl rollout status deployments redis -n dojot | grep successfully
    do
      sleep 1
    done

    slaves=$(kubectl -n dojot exec redis-bootstrap -- redis-cli info | grep connected_slaves | cut -d ':' -f 2 | cut -c 1)

    until [ ${slaves} == "3" ];
    do
      sleep 2
      slaves=$(kubectl -n dojot exec redis-bootstrap -- redis-cli info | grep connected_slaves | cut -d ':' -f 2 | cut -c 1)
    done

    kubectl delete -n dojot pod redis-bootstrap

    # Changes the external ip back to a placeholder
    sed -i "s/${EXTERNAL_IP}/\[EXTERNAL_IP\]/g" manifests/LOCAL/external-access.yaml
    sed -i "s/monitors:.*/monitors: \[CEPH_MONITORS\]/g" manifests/LOCAL/*.yaml

elif [ ${DEPLOY_TYPE} = "GCP" ]; then
    TAG=${2:-latest}

    sed -i -r "s/(dojot\/[a-zA-Z\-]+).*/\1:${TAG}/g" manifests/*.yaml

    echo "Starting Deployment Server"

    sudo python3 google_cloud.py

else
    print_error
fi
