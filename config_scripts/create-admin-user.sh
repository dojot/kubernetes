#!/bin/bash

auth="http://auth:5000/user"
kong="http://kong:8001"

echo "Waiting for auth service to be up"

# Wait for auth to be up
until [ $(curl -X POST -w '%{http_code}\n' --fail --silent --header "content-type: application/json" -d "{}" ${auth}) -eq 400 ]; do
    printf '.'
    sleep 2
done

echo "Waiting for kong service to be up"

# Wait for kong to be up
until $(curl --output /dev/null --silent --head --fail ${kong}); do
    printf '.'
    sleep 2
done

echo
echo "Services are up, configuring user"

curl $auth -sS -X POST \
    --header "content-type: application/json" \
    -d @- <<PAYLOAD
{
    "username": "admin",
    "passwd":"admin",
    "service":"admin",
    "email":"admin@noemail.com",
    "name":"Admin (superuser)",
    "profile": "admin"
}
PAYLOAD

echo
echo "User configured"