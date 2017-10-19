#! python3
# -*- coding: utf-8 -*-

import os
import flask
import requests
import time
import yaml

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from googleapiclient.errors import HttpError

from kubernetes import client, config

# This variable specifies the name of a file that contains the OAuth 2.0
# information for this application, including its client_id and client_secret.
from kubernetes.client.rest import ApiException

CLIENT_SECRETS_FILE = "client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

CLOUD_RESOURCES_API_SERVICE_NAME = 'cloudresourcemanager'
CLOUD_RESOURCES_API_VERSION = 'v1'

CONTAINERS_API_SERVICE_NAME = 'container'
CONTAINERS_API_VERSION = 'v1'

app = flask.Flask(__name__)

DOJOT_CLUSTER = "dojot-cluster"
DOJOT_ZONE = "southamerica-east1-b"

DEPLOYMENTS_LIST = [
    'apigw.yaml',
    'auth.yaml',
    'coap.yaml',
    'device-manager.yaml',
    'gui.yaml',
    'iotagent.yaml',
    'mashup.yaml',
    'GCP/mongo.yaml',
    'mqtt.yaml',
    'orion.yaml',
    'perseo-core.yaml',
    'perseo-fe.yaml',
    'GCP/postgres.yaml',
    'sth.yaml'
]

SERVICES_LIST = [
    'apigw-service.yaml',
    'auth-service.yaml',
    'coap-service.yaml',
    'GCP/external-access.yaml',
    'device-manager-service.yaml',
    'gui-service.yaml',
    'iotagent-service.yaml',
    'mashup-service.yaml',
    'mongo-service.yaml',
    'mqtt-service.yaml',
    'orion-service.yaml',
    'perseo-core-service.yaml',
    'perseo-fe-service.yaml',
    'postgres-service.yaml',
    'sth-service.yaml'
]

JOBS_LIST = [
    'apigw-job.yaml',
    'kong-route-config-job.yaml',
    'create-admin-user-job.yaml'
]

VOLUMES_LIST = [
    'GCP/mongo-volume.yaml',
    'GCP/postgres-volume.yaml'
]

app.secret_key = '\x8a\x17\xebrC\xe5a\xb5\x0f:0\x8b\xd6\xed\xb3L\xe5lH\xbc2w\xd6L'


@app.route('/')
def index():
    return print_index_table()


@app.route('/authenticate')
def deploy_request():
    if 'credentials' not in flask.session:
        return flask.redirect('authorize')

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    cloud_resources = googleapiclient.discovery.build(
        CLOUD_RESOURCES_API_SERVICE_NAME,
        CLOUD_RESOURCES_API_VERSION,
        credentials=credentials)

    # project_id = flask.session.get('project', '')

    projects = cloud_resources.projects().list().execute()

    active_projects = []

    for project in projects['projects']:
        if project['lifecycleState'] == 'ACTIVE':
            active_projects.append(project['projectId'])

    return_page = 'Authentication Completed!.<br><br>' + \
                  'Step 2 - Select the project where dojot will be deployed: <br>'

    for project in active_projects:
        return_page = return_page + '<a href = "/deploy/' + project + '" > ' + project + '</a> <br>'

    return return_page


@app.route('/deploy/<project_id>')
def cluster_creation(project_id):

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    container = googleapiclient.discovery.build(
        CONTAINERS_API_SERVICE_NAME,
        CONTAINERS_API_VERSION,
        credentials=credentials)

    # Create a simple cluster
    try:
        container.projects().zones().clusters().get(
            projectId=project_id,
            zone=DOJOT_ZONE,
            clusterId=DOJOT_CLUSTER
        ).execute()
    except HttpError as error:
        if error.resp['status'] == '404':
            container.projects().zones().clusters().create(
                projectId=project_id,
                zone=DOJOT_ZONE,
                body={
                    "cluster": {
                        "name": DOJOT_CLUSTER,
                        "zone": DOJOT_ZONE,
                        "network": "default",
                        "loggingService": "logging.googleapis.com",
                        "monitoringService": "monitoring.googleapis.com",
                        "nodePools": [
                            {
                                "name": "default-pool",
                                "initialNodeCount": 3,
                                "config": {
                                    "machineType": "n1-standard-1",
                                    "imageType": "COS",
                                    "diskSizeGb": 30,
                                    "preemptible": False,
                                    "oauthScopes": [
                                        "https://www.googleapis.com/auth/compute",
                                        "https://www.googleapis.com/auth/devstorage.read_only",
                                        "https://www.googleapis.com/auth/logging.write",
                                        "https://www.googleapis.com/auth/monitoring",
                                        "https://www.googleapis.com/auth/servicecontrol",
                                        "https://www.googleapis.com/auth/service.management.readonly",
                                        "https://www.googleapis.com/auth/trace.append"
                                    ]
                                },
                                "autoscaling": {
                                    "enabled": False
                                },
                                "management": {
                                    "autoUpgrade": False,
                                    "autoRepair": False,
                                    "upgradeOptions": {}
                                }
                            }
                        ],
                        "initialClusterVersion": "1.7.6-gke.1",
                        "masterAuth": {
                            "username": "admin",
                            "clientCertificateConfig": {
                                "issueClientCertificate": True
                            }
                        },
                        "subnetwork": "default",
                        "legacyAbac": {
                            "enabled": True
                        },
                        "masterAuthorizedNetworksConfig": {
                            "enabled": False,
                            "cidrBlocks": []
                        },
                        "addonsConfig": {
                            "kubernetesDashboard": {
                                "disabled": False
                            },
                            "httpLoadBalancing": {
                                "disabled": False
                            },
                            "networkPolicyConfig": {
                                "disabled": True
                            }
                        },
                        "networkPolicy": {
                            "enabled": False,
                            "provider": "CALICO"
                        },
                        "ipAllocationPolicy": {
                            "useIpAliases": False
                        }
                    }
                }).execute()
        else:
            raise error

    status = "Empty"

    while "RUNNING" not in status:
        time.sleep(5)

        cluster = container.projects().zones().clusters().get(
            projectId=project_id,
            zone=DOJOT_ZONE,
            clusterId=DOJOT_CLUSTER
        ).execute()

        status = cluster.get('status')
        print(status)

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
        **flask.session['credentials'])

    container = googleapiclient.discovery.build(
        CONTAINERS_API_SERVICE_NAME,
        CONTAINERS_API_VERSION,
        credentials=credentials)

    cluster = container.projects().zones().clusters().get(
        projectId=project_id,
        zone=DOJOT_ZONE,
        clusterId=DOJOT_CLUSTER
    ).execute()

    kube_ca = cluster['masterAuth']['clusterCaCertificate']
    kube_user = cluster['masterAuth']['username']
    kube_server = cluster['endpoint']
    kube_cc = cluster['masterAuth']['clientCertificate']
    kube_ck = cluster['masterAuth']['clientKey']

    file = open('client_config', 'w')

    file.writelines(
        ['apiVersion: v1\n',
         'kind: Config\n',
         'clusters:\n',
         '- cluster:\n',
         '    certificate-authority-data: ' + kube_ca + '\n',
         '    server: https://' + kube_server + '\n',
         '  name: dojot-cluster\n',
         'current-context: dojot-cluster-context\n',
         'contexts:\n',
         '- context:\n',
         '    cluster: dojot-cluster\n',
         '    user: ' + kube_user + '\n',
         '  name: dojot-cluster-context\n',
         'users:\n',
         '- name: ' + kube_user + '\n',
         '  user: \n',
         '    client-certificate-data: ' + kube_cc + '\n',
         '    client-key-data: ' + kube_ck + '\n'
         ])

    file.close()

    api_client = config.new_client_from_config(config_file='client_config')

    api_instance = client.CoreV1Api(api_client=api_client)
    api_instance_beta = client.ExtensionsV1beta1Api(api_client=api_client)
    api_instance_batch = client.BatchV1Api(api_client=api_client)

    # Create the dojot namespace
    try:
        api_instance.read_namespace(name="dojot")
    except ApiException:
        namespace = client.V1Namespace()
        namespace.metadata = client.V1ObjectMeta(name="dojot")

        api_instance.create_namespace(body=namespace)

    # Create the configmaps
    cmap = client.V1ConfigMap()

    try:
        api_instance.read_namespaced_config_map(name="iotagent-conf", namespace="dojot")
    except ApiException:
        cmap.metadata = client.V1ObjectMeta(name="iotagent-conf")
        cmap.data = {"config.js": open('iotagent/config.js').read()}
        api_instance.create_namespaced_config_map(namespace="dojot", body=cmap)

    try:
        api_instance.read_namespaced_config_map(name="kong-route-config", namespace="dojot")
    except ApiException:
        cmap.metadata = client.V1ObjectMeta(name="kong-route-config")
        cmap.data = {"kong.config.sh": open('config_scripts/kong.config.sh').read()}
        api_instance.create_namespaced_config_map(namespace="dojot", body=cmap)

    try:
        api_instance.read_namespaced_config_map(name="create-admin-user", namespace="dojot")
    except ApiException:
        cmap.metadata = client.V1ObjectMeta(name="create-admin-user")
        cmap.data = {"create-admin-user.sh": open('config_scripts/create-admin-user.sh').read()}
        api_instance.create_namespaced_config_map(namespace="dojot", body=cmap)

    for volume in VOLUMES_LIST:
        with open("manifests/" + volume) as f:
            dep = yaml.load(f)

            object_name = dep['metadata']['name']
            try:
                api_instance.read_namespaced_persistent_volume_claim(name=object_name, namespace="dojot")
            except ApiException:
                api_instance.create_namespaced_persistent_volume_claim(body=dep, namespace="dojot")

    for deployment in DEPLOYMENTS_LIST:
        with open("manifests/" + deployment) as f:
            dep = yaml.load(f)

            object_name = dep['metadata']['name']
            try:
                api_instance_beta.read_namespaced_deployment(name=object_name, namespace="dojot")
            except ApiException:
                api_instance_beta.create_namespaced_deployment(body=dep, namespace="dojot")

    for service in SERVICES_LIST:
        with open("manifests/" + service) as f:
            dep = yaml.load(f)

            object_name = dep['metadata']['name']
            try:
                api_instance.read_namespaced_service(name=object_name, namespace="dojot")
            except ApiException:
                api_instance.create_namespaced_service(body=dep, namespace="dojot")

    for job in JOBS_LIST:
        with open("manifests/" + job) as f:
            dep = yaml.load(f)

            object_name = dep['metadata']['name']
            try:
                api_instance_batch.read_namespaced_job(name=object_name, namespace="dojot")
            except ApiException:
                api_instance_batch.create_namespaced_job(body=dep, namespace="dojot")

    print("Waiting for job completion")

    all_succeeded = False

    while all_succeeded is False:
        time.sleep(10)
        jobs = api_instance_batch.list_namespaced_job(namespace='dojot')

        success_count = 0
        number_of_jobs = len(jobs.items)

        for job in jobs.items:
            if job.status.succeeded is not None and job.status.succeeded > 0:
                success_count += 1

        print("Completed Jobs: " + str(success_count))

        if success_count == number_of_jobs:
            all_succeeded = True

    print("Jobs completed")

    external_service = api_instance.read_namespaced_service(name="external", namespace="dojot")

    external_ip = external_service.status.load_balancer.ingress[0].ip

    return ('Containers Started.<br><br>' +
            'To access your dojot deployment, go to the link: <a href="http://' + external_ip + '">DOJOT</a><br><br>')


@app.route('/authorize')
def authorize():
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)

    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    flask.session['state'] = state

    return flask.redirect(authorization_url)


@app.route('/oauth2callback')
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = flask.session['state']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = flask.request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    flask.session['credentials'] = credentials_to_dict(credentials)

    return flask.redirect(flask.url_for('deploy_request'))


@app.route('/clear')
def clear_credentials():

    if 'credentials' in flask.session:

        credentials = google.oauth2.credentials.Credentials(
            **flask.session['credentials'])

        requests.post('https://accounts.google.com/o/oauth2/revoke',
                      params={'token': credentials.token},
                      headers={'content-type': 'application/x-www-form-urlencoded'})

    flask.session.clear()

    return ('Credentials have been cleared.<br><br>' +
            print_index_table())


def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}


def print_index_table():
    return ('<table>' +
            '<tr><td><a href="/authenticate">Deploy dojot to Google Cloud - Step 1</a></td>' +
            '<td>Authenticate and select a project. ' +
            '</td></tr>' +
            '<tr><td><a href="/clear">Clear Flask session credentials</a></td>' +
            '<td> Revoke access to the cloud platform and clear session data' +
            '</td></tr>' +
            '</table>')


if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'

    app.run('0.0.0.0', 8080, debug=True, threaded=True)
