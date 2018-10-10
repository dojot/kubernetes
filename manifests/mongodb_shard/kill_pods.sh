re='^[0-9]+$'
if [ "$1" == "" ]; then
    export N_SHARDS=3
elif ! [[ $1 =~ $re ]]; then
    echo "insert a valid integer"
    exit 1
else
    export N_SHARDS=$1
fi

kubectl delete -f mongos.yaml
kubectl delete -f mongocfg.yaml

for ((i=0;i<N_SHARDS;i++)); do
    kubectl delete -f mongosh$i.yaml
    rm mongosh$i.yaml
done