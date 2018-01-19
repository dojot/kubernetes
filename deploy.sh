#!/bin/bash

TAG=latest

function print_error {
    cat <<-EOF
Usage: ./deploy.sh STORAGE_TYPE EXTERNAL_ACCESS_TYPE

The storage that will be used for deployment must be selected from the following options: CEPH or GCP
 - If Ceph is selected you will be prompted for the path for the a file containing Ceph configuration

The external access must be selected from the following options, PUBLIC_IP or LB
 - If public ip is selected you will be prompted for the ip address to be used

The dojot version that will be deployed is the ${TAG} version
EOF
    exit
}

# Check if parameters are set
if [ $# -lt 2 ]; then
    print_error
fi

STORAGE_TYPE=${1}
EXTERNAL_ACCESS_TYPE=${2}

echo Starting Deployment

# Create the dojot namespace
kubectl create namespace dojot

if [ ${STORAGE_TYPE} = "CEPH" ]; then
    echo "Enter the path to a Ceph configuration file:"
    read ceph_file
    CEPH_MON_IPS=$(grep mon_host ${ceph_file} | egrep -o "[0-9\.\,]+" | sed -r "s/[0-9\.]+/\0:6789/g")

    # Update the ceph monitor adresses for the volumes
    sed -i -r "s/\[CEPH_MONITORS\]/${CEPH_MON_IPS}/g" manifests/STORAGE/CEPH/dojot-storage-class.yaml

    kubectl create -f manifests/STORAGE/CEPH/ceph-secret-user.yaml
    kubectl create -n kube-system -f manifests/STORAGE/CEPH/ceph-secret-admin.yaml
    kubectl create -f manifests/STORAGE/CEPH/dojot-storage-class.yaml

    # Provides authorization for the rbd manager, requires admin access
    kubectl create -f manifests/STORAGE/CEPH/rbd-provisioner.yaml

    sed -i "s/monitors:.*/monitors: \[CEPH_MONITORS\]/g" manifests/STORAGE/CEPH/dojot-storage-class.yaml

elif [ ${STORAGE_TYPE} = "GCP" ]; then
    kubectl create -f manifests/STORAGE/GCP/dojot-storage-class.yaml
else
    print_error
fi

if [ ${EXTERNAL_ACCESS_TYPE} = "PUBLIC_IP" ]; then
    echo "Enter the public ip address that will be used for external access: "
    read public_ip
    # Update the public ip
    sed -i "s/\[EXTERNAL_IP\]/${public_ip}/g" manifests/EXTERNAL_ACCESS/public-ip.yaml

    kubectl create -f manifests/EXTERNAL_ACCESS/public-ip.yaml

    # Changes the external ip back to a placeholder
    sed -i "s/${public_ip}/\[EXTERNAL_IP\]/g" manifests/EXTERNAL_ACCESS/public-ip.yaml

elif [ ${EXTERNAL_ACCESS_TYPE} = "LB" ]; then

    kubectl create -f manifests/EXTERNAL_ACCESS/load-balancer.yaml

else
    print_error
fi

# Update the tag of the containers
sed -i -r "s/( dojot\/[a-zA-Z\-]+).*/\1:${TAG}/g" manifests/*.yaml

# Create configuration files mappings
kubectl create -n dojot configmap iotagent-conf --from-file=iotagent/config.json
kubectl create -n dojot configmap kong-route-config --from-file=config_scripts/kong.config.sh
kubectl create -n dojot configmap postgres-init --from-file=config_scripts/postgres-init.sh

# Deploy Dojot services
kubectl create -f manifests/

echo Deployment is complete!
