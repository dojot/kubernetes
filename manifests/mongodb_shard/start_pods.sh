# checks if positional argument is an integer
re='^[0-9]+$'
if [ "$1" == "" ]; then
    echo "defaulting to N_SHARDS=3"
    export N_SHARDS=3
elif ! [[ $1 =~ $re ]]; then
    echo "insert a valid integer"
    exit 1
else
    export N_SHARDS=$1
fi

echo "creating namespace"
kubectl create namespace dojot

# creates new yaml file for each shard
echo "starting $N_SHARDS shard replicas"
for ((i=0;i<N_SHARDS;i++)); do
    cp mongosh.yaml mongosh$i.yaml
    sed -i -e "s/mongosh./mongosh$i/g" mongosh$i.yaml
    sed -i -e "s/- rs./- rs$i/g" mongosh$i.yaml
    kubectl -n dojot apply -f mongosh$i.yaml
done

echo "starting config server replica"
kubectl -n dojot apply -f mongocfg.yaml

# needs to wait enough time for all pods to be running
echo "waiting for initialization to finish"
sleep 2m

# applies config servers endpoints to mongos.yaml file
echo "starting mongos"
export CONFIG_ENDPOINTS=$(kubectl -n dojot get endpoints mongocfg | grep mongocfg | awk '{print $2}')
sed -i '/configReplSet/c\        - configReplSet/'"$CONFIG_ENDPOINTS" mongos.yaml
kubectl -n dojot apply -f mongos.yaml

# needs to wait enough time for mongos pod to be running
sleep 20

# adds endpoints for each shard (replica set) to mongos
echo "adding shards to mongos"
for ((i=0;i<N_SHARDS;i++)); do
    kubectl -n dojot exec mongodb-0 -c mongodb -- mongo --eval "sh.addShard('rs$i/$(kubectl -n dojot get endpoints mongosh$i | grep mongosh$i | awk '{print $2}')')"
done

