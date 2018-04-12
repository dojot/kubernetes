import logging
import base64
import yaml

from .kube import KubeClient

logger = logging.getLogger("Deployer")


class KubeDeployer:

    def __init__(self, conf):
        self.config = conf
        self.kube_client = KubeClient()

    def deploy_rbd(self, namespace):

        with open('manifests/STORAGE/CEPH/rbd-provisioner.yaml',
                  'r') as rbd_model:

            for rbd_data in yaml.load_all(rbd_model):

                if rbd_data["kind"] == "Deployment":
                    spec = rbd_data["spec"]
                    name = rbd_data["metadata"]["name"]
                    rbd_namespace = rbd_data["metadata"]["namespace"]
                    self.kube_client.create_deployment(name, rbd_namespace, spec)
                elif rbd_data["kind"] == "ServiceAccount":
                    name = rbd_data["metadata"]["name"]
                    sa_namespace = rbd_data["metadata"]["namespace"]
                    if sa_namespace != 'kube-system':
                        sa_namespace = namespace
                    self.kube_client.create_service_account(name, sa_namespace)
                elif rbd_data["kind"] == "ClusterRole":
                    name = rbd_data["metadata"]["name"]
                    rules = rbd_data["rules"]
                    self.kube_client.create_cluster_role(name, rules)
                elif rbd_data["kind"] == "ClusterRoleBinding":
                    name = rbd_data["metadata"]["name"]
                    subjects = rbd_data["subjects"]
                    cluster_role = rbd_data["roleRef"]["name"]

                    for subject in subjects:
                        if subject['namespace'] != 'kube-system':
                            subject['namespace'] = namespace

                    self.kube_client.create_cluster_role_binding(name, subjects, cluster_role)
                else:
                    logger.warning("Found unexpected object on RBD model file!")

    def configure_storage(self, namespace):
        storage = self.config.get_config_data('storage')

        if storage['type'] == 'ceph':

            ceph_monitors = storage['cephMonitors']
            admin_id = storage['cephAdminId']
            admin_key = storage['cephAdminKey']
            user_id = storage['cephUserId']
            user_key = storage['cephUserKey']
            user_pool = storage['cephPoolName']

            self.kube_client.create_secret('ceph-secret-admin', 'kubernetes.io/rbd',
                                           'kube-system', {'key': base64.b64encode(
                                               admin_key.encode()).decode()})
            self.kube_client.create_secret('ceph-secret-user', 'kubernetes.io/rbd',
                                           namespace, {'key': base64.b64encode(
                                               user_key.encode()).decode()})

            with open('manifests/STORAGE/CEPH/dojot-storage-class.yaml', 'r') as st_class:
                st_data = yaml.load(st_class)

                name = st_data['metadata']['name']
                provisioner = st_data['provisioner']
                parameters = st_data['parameters']

                parameters['monitors'] = \
                    str(ceph_monitors).strip("[]").replace("'", "").replace(" ", "")
                parameters['userId'] = user_id
                parameters['adminId'] = admin_id
                parameters['pool'] = user_pool

                self.kube_client.create_storage_class(name, {'provisioner': provisioner,
                                                             'parameters': parameters})

            self.deploy_rbd(namespace)

        elif storage['type'] == 'gcp':

            gcp_storage_type = storage['gcpStorageType']

            with open('manifests/STORAGE/GCP/dojot-storage-class.yaml', 'r') as st_class:
                st_data = yaml.load(st_class)

                name = st_data['metadata']['name']
                provisioner = st_data['provisioner']
                parameters = st_data['parameters']

                parameters['type'] = gcp_storage_type
                self.kube_client.create_storage_class(name, {'provisioner': provisioner,
                                                             'parameters': parameters})

    def configure_external_access(self, namespace):
        external = self.config.get_config_data('externalAccess')

        external_ports = external['ports']

        if external['type'] == 'publicIP':
            ips_list = external['ips']

            with open('manifests/EXTERNAL_ACCESS/public-ip.yaml', 'r') as external_file:
                for service_doc in yaml.load_all(external_file):
                    service_name = service_doc['metadata']['name']
                    service_spec = service_doc['spec']

                    service_spec['externalIPs'] = ips_list
                    service_ports = service_spec['ports']

                    for port in service_ports:
                        if port['name'] == 'ext-http':
                            port['port'] = external_ports['httpPort']
                        elif port['name'] == 'ext-https':
                            port['port'] = external_ports['httpsPort']
                        elif port['name'] == 'ext-mqtt':
                            port['port'] = external_ports['mqttPort']
                        elif port['name'] == 'ext-coap':
                            port['port'] = external_ports['coapPort']

                    self.kube_client.create_service(service_name, namespace, service_spec)

        elif external['type'] == 'loadBalancer':

            with open('manifests/EXTERNAL_ACCESS/load-balancer.yaml', 'r') as external_file:
                for service_doc in yaml.load_all(external_file):
                    service_name = service_doc['metadata']['name']
                    service_spec = service_doc['spec']

                    service_ports = service_spec['ports']

                    for port in service_ports:
                        if port['name'] == 'ext-http':
                            port['port'] = external_ports['httpPort']
                        elif port['name'] == 'ext-https':
                            port['port'] = external_ports['httpsPort']
                        elif port['name'] == 'ext-mqtt':
                            port['port'] = external_ports['mqttPort']
                        elif port['name'] == 'ext-coap':
                            port['port'] = external_ports['coapPort']

                    self.kube_client.create_service(service_name, namespace, service_spec)

    def deploy_zookeeper(self, namespace, config):

        zk_size = config['clusterSize']

        with open('manifests/zookeeper.yaml', 'r') as zk_docs:

            for zk_doc in yaml.load_all(zk_docs):

                if zk_doc['kind'] == 'Service':
                    self.kube_client.create_service(zk_doc['metadata']['name'],
                                                    namespace, zk_doc['spec'])

                elif zk_doc['kind'] == 'StatefulSet':

                    zk_spec = zk_doc['spec']

                    zk_spec['replicas'] = zk_size
                    zk_spec['template']['spec']['containers'][0]['command'][-1] = \
                        "--servers=%d" % zk_size

                    self.kube_client.create_stateful_set(zk_doc['metadata']['name'],
                                                         namespace, zk_spec)
                else:
                    logger.error("Invalid document on Zookeeper manifest: %s" % zk_doc['kind'])

    def deploy_postgres(self, namespace, config):

        pg_size = config['clusterSize']

        with open('config_scripts/postgres-init.sh', 'r') as config_file:

            config_data = {
                "postgres-init.sh": config_file.read()
            }

            self.kube_client.create_config_map('postgres-init', namespace, config_data)

        with open('manifests/postgres.yaml', 'r') as pg_docs:

            for pg_doc in yaml.load_all(pg_docs):

                if pg_doc['kind'] == 'ServiceAccount':
                    self.kube_client.create_service_account(pg_doc['metadata']['name'], namespace)
                elif pg_doc['kind'] == 'Role':
                    self.kube_client.create_role(pg_doc['metadata']['name'], namespace,
                                                 pg_doc['rules'])
                elif pg_doc['kind'] == 'RoleBinding':
                    self.kube_client.create_role_binding(pg_doc['metadata']['name'],
                                                         namespace,
                                                         pg_doc['subjects'],
                                                         pg_doc['roleRef']['name'])
                elif pg_doc['kind'] == 'Service':
                    self.kube_client.create_service(pg_doc['metadata']['name'], namespace,
                                                    pg_doc['spec'])
                elif pg_doc['kind'] == 'StatefulSet':

                    pg_spec = pg_doc['spec']

                    pg_spec['replicas'] = pg_size

                    for env_var in pg_spec['template']['spec']['containers'][0]['env']:
                        if env_var['name'] == 'POD_NAMESPACE':
                            env_var['value'] = namespace

                    # TODO: Get passwoords as secrets

                    self.kube_client.create_stateful_set(pg_doc['metadata']['name'],
                                                         namespace, pg_spec)
                elif pg_doc['kind'] == 'Job':

                    # TODO: Passwords as secrets
                    self.kube_client.start_job(pg_doc['metadata']['name'], namespace,
                                               pg_doc['spec'])
                else:
                    logger.error("Invalid document on Postgres manifest: %s" % pg_doc['kind'])

    def deploy_mongodb(self, namespace, config):

        mongodb_replicas = config['replicas']

        with open('manifests/mongodb.yaml', 'r') as mongodb_docs:

            for mongodb_doc in yaml.load_all(mongodb_docs):

                if mongodb_doc['kind'] == 'ServiceAccount':
                    self.kube_client.create_service_account(
                        mongodb_doc['metadata']['name'], namespace)
                elif mongodb_doc['kind'] == 'Role':
                    self.kube_client.create_role(mongodb_doc['metadata']['name'], namespace,
                                                 mongodb_doc['rules'])
                elif mongodb_doc['kind'] == 'RoleBinding':
                    self.kube_client.create_role_binding(mongodb_doc['metadata']['name'],
                                                         namespace,
                                                         mongodb_doc['subjects'],
                                                         mongodb_doc['roleRef']['name'])
                elif mongodb_doc['kind'] == 'Service':
                    self.kube_client.create_service(mongodb_doc['metadata']['name'], namespace,
                                                    mongodb_doc['spec'])
                elif mongodb_doc['kind'] == 'StatefulSet':

                    mongodb_spec = mongodb_doc['spec']

                    mongodb_spec['replicas'] = 1 + mongodb_replicas

                    for env_var in mongodb_spec['template']['spec']['containers'][1]['env']:
                        if env_var['name'] == 'KUBE_NAMESPACE':
                            env_var['value'] = namespace

                    self.kube_client.create_stateful_set(mongodb_doc['metadata']['name'],
                                                         namespace, mongodb_spec)
                else:
                    logger.error("Invalid document on MongoDB manifest: %s" % mongodb_doc['kind'])

    def deploy_kafka(self, namespace, config):

        kafka_replicas = config['clusterSize']

        with open('manifests/kafka.yaml', 'r') as kafka_docs:

            for kafka_doc in yaml.load_all(kafka_docs):

                if kafka_doc['kind'] == 'Service':
                    self.kube_client.create_service(kafka_doc['metadata']['name'], namespace,
                                                    kafka_doc['spec'])
                elif kafka_doc['kind'] == 'StatefulSet':

                    kafka_spec = kafka_doc['spec']

                    kafka_spec['replicas'] = kafka_replicas

                    self.kube_client.create_stateful_set(kafka_doc['metadata']['name'],
                                                         namespace, kafka_spec)
                else:
                    logger.error("Invalid document on Kafka manifest: %s" % kafka_doc['kind'])

    def deploy_device_manager(self, namespace):

        with open('manifests/device_manager.yaml', 'r') as devm_docs:

            for devm_doc in yaml.load_all(devm_docs):
                if devm_doc['kind'] == 'Service':
                    self.kube_client.create_service(devm_doc['metadata']['name'], namespace,
                                                    devm_doc['spec'])
                elif devm_doc['kind'] == 'Deployment':

                    if devm_doc['metadata']['name'] == "device-manager":
                        image = devm_doc['spec']['template']['spec']['containers'][0]['image']

                        image = image.replace('latest', self.config.get_config_data('version'))

                        devm_doc['spec']['template']['spec']['containers'][0]['image'] = image

                    self.kube_client.create_deployment(devm_doc['metadata']['name'], namespace,
                                                       devm_doc['spec'])
                else:
                    logger.error("Invalid document on Dev Manager manifest: %s" % devm_doc['kind'])

    def deploy_data_broker(self, namespace):

        with open('manifests/data_broker.yaml', 'r') as data_broker_docs:

            for db_doc in yaml.load_all(data_broker_docs):
                if db_doc['kind'] == 'Service':
                    self.kube_client.create_service(db_doc['metadata']['name'], namespace,
                                                    db_doc['spec'])
                elif db_doc['kind'] == 'Deployment':

                    if db_doc['metadata']['name'] == "data-broker":
                        img = db_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                            'latest', self.config.get_config_data('version'))

                        db_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(db_doc['metadata']['name'], namespace,
                                                       db_doc['spec'])
                else:
                    logger.error("Invalid document on Data Broker manifest: %s" % db_doc['kind'])

    def deploy_gui(self, namespace):

        with open('manifests/gui.yaml', 'r') as gui_docs:

            for gui_doc in yaml.load_all(gui_docs):
                if gui_doc['kind'] == 'Service':
                    self.kube_client.create_service(gui_doc['metadata']['name'], namespace,
                                                    gui_doc['spec'])
                elif gui_doc['kind'] == 'Deployment':

                    img = gui_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                        'latest', self.config.get_config_data('version'))

                    gui_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(gui_doc['metadata']['name'], namespace,
                                                       gui_doc['spec'])
                else:
                    logger.error("Invalid document on GUI manifest: %s" % gui_doc['kind'])

    def deploy_apigw(self, namespace):

        with open('config_scripts/kong.config.sh', 'r') as config_file:

            config_data = {
                "kong.config.sh": config_file.read()
            }

            self.kube_client.create_config_map('kong-route-config', namespace, config_data)

        with open('manifests/apigw.yaml', 'r') as apigw_docs:

            for apigw_doc in yaml.load_all(apigw_docs):

                if apigw_doc['kind'] == 'Service':
                    self.kube_client.create_service(apigw_doc['metadata']['name'], namespace,
                                                    apigw_doc['spec'])
                elif apigw_doc['kind'] == 'Deployment':

                    img = apigw_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                        'latest', self.config.get_config_data('version'))

                    apigw_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(apigw_doc['metadata']['name'], namespace,
                                                       apigw_doc['spec'])

                elif apigw_doc['kind'] == 'Job':

                    if apigw_doc['metadata']['name'] == "kong-migrate":
                        img = \
                            apigw_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                                'latest', self.config.get_config_data('version'))

                        apigw_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.start_job(apigw_doc['metadata']['name'], namespace,
                                               apigw_doc['spec'])
                else:
                    logger.error("Invalid document on API GW manifest: %s" % apigw_doc['kind'])

    def deploy_auth(self, namespace, config):

        with open('manifests/auth.yaml', 'r') as auth_docs:

            for auth_doc in yaml.load_all(auth_docs):
                if auth_doc['kind'] == 'Service':
                    self.kube_client.create_service(auth_doc['metadata']['name'], namespace,
                                                    auth_doc['spec'])
                elif auth_doc['kind'] == 'Deployment':

                    img = auth_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                        'latest', self.config.get_config_data('version'))

                    auth_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    # If email parameters are set, pass then to the deployment
                    # TODO: Set email parameters as secrets
                    if config.get('emailHost', None):

                        env_vars = auth_doc['spec']['template']['spec']['containers'][0]['env']

                        for env_var in env_vars:
                            if env_var['name'] == 'AUTH_EMAIL_HOST':
                                env_var['value'] = config.get('emailHost')
                            elif env_var['name'] == 'AUTH_EMAIL_USER':
                                env_var['value'] = config.get('emailUser')
                            elif env_var['name'] == 'AUTH_EMAIL_PASSWD':
                                env_var['value'] = config.get('emailPassword')

                    self.kube_client.create_deployment(auth_doc['metadata']['name'], namespace,
                                                       auth_doc['spec'])
                else:
                    logger.error("Invalid document on Auth manifest: %s" % auth_doc['kind'])

    # TODO: Make cluster size configurable
    def deploy_rabbitmq(self, namespace):
        with open('manifests/rabbitmq.yaml', 'r') as rabbit_docs:

            for rabbit_doc in yaml.load_all(rabbit_docs):

                if rabbit_doc['kind'] == 'ServiceAccount':
                    self.kube_client.create_service_account(
                        rabbit_doc['metadata']['name'], namespace)
                elif rabbit_doc['kind'] == 'Role':
                    self.kube_client.create_role(rabbit_doc['metadata']['name'], namespace,
                                                 rabbit_doc['rules'])
                elif rabbit_doc['kind'] == 'RoleBinding':
                    self.kube_client.create_role_binding(rabbit_doc['metadata']['name'],
                                                         namespace,
                                                         rabbit_doc['subjects'],
                                                         rabbit_doc['roleRef']['name'])
                elif rabbit_doc['kind'] == 'ConfigMap':
                    self.kube_client.create_config_map(rabbit_doc['metadata']['name'], namespace,
                                                       rabbit_doc['data'])
                elif rabbit_doc['kind'] == 'Service':
                    self.kube_client.create_service(rabbit_doc['metadata']['name'], namespace,
                                                    rabbit_doc['spec'])
                elif rabbit_doc['kind'] == 'StatefulSet':

                    self.kube_client.create_stateful_set(rabbit_doc['metadata']['name'], namespace,
                                                         rabbit_doc['spec'])
                else:
                    logger.error("Invalid document on RabbitMQ manifest: %s" % rabbit_doc['kind'])

    def deploy_mqtt_iotagent(self, namespace):
        with open('manifests/iotagent-mqtt.yaml', 'r') as mqtt_docs:

            for mqtt_doc in yaml.load_all(mqtt_docs):
                if mqtt_doc['kind'] == 'Service':

                    self.kube_client.create_service(mqtt_doc['metadata']['name'], namespace,
                                                    mqtt_doc['spec'])
                elif mqtt_doc['kind'] == 'Deployment':

                    if mqtt_doc['metadata']['name'] == "iotagent-mqtt":
                        img = \
                            mqtt_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                                'latest', self.config.get_config_data('version'))

                        mqtt_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(mqtt_doc['metadata']['name'], namespace,
                                                       mqtt_doc['spec'])
                else:
                    logger.error("Invalid document on MQTT IoT Agent manifest: %s" %
                                 mqtt_doc['kind'])

    def deploy_flowbroker(self, namespace):
        with open('manifests/flowbroker.yaml', 'r') as flowbroker_docs:

            for flowbroker_doc in yaml.load_all(flowbroker_docs):
                if flowbroker_doc['kind'] == 'Service':

                    self.kube_client.create_service(flowbroker_doc['metadata']['name'], namespace,
                                                    flowbroker_doc['spec'])
                elif flowbroker_doc['kind'] == 'Deployment':

                    img = \
                      flowbroker_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                            'latest', self.config.get_config_data('version'))

                    flowbroker_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(flowbroker_doc['metadata']['name'],
                                                       namespace, flowbroker_doc['spec'])
                else:
                    logger.error("Invalid document on Flowbroker manifest: %s" %
                                 flowbroker_doc['kind'])

    def deploy_history(self, namespace):
        with open('manifests/history.yaml', 'r') as history_docs:

            for history_doc in yaml.load_all(history_docs):
                if history_doc['kind'] == 'Service':

                    self.kube_client.create_service(history_doc['metadata']['name'], namespace,
                                                    history_doc['spec'])
                elif history_doc['kind'] == 'Deployment':

                    img = \
                      history_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                            'latest', self.config.get_config_data('version'))

                    history_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(history_doc['metadata']['name'],
                                                       namespace, history_doc['spec'])
                else:
                    logger.error("Invalid document on History manifest: %s" %
                                 history_doc['kind'])

    def deploy_mutual_auth(self, namespace):

        with open('ma_config_files/redis_init.sh', 'r') as redis_init_file:
            redis_init = redis_init_file.read()

        with open('ma_config_files/redis.conf', 'r') as redis_conf_file:
            redis_conf = redis_conf_file.read()

        with open('ma_config_files/sentinel.conf', 'r') as sentinel_conf_file:
            sentinel_conf = sentinel_conf_file.read()

        config_data = {
            "sentinel.conf": sentinel_conf,
            "redis.conf": redis_conf,
            "redis_init.sh": redis_init
        }

        self.kube_client.create_config_map('ma-redis-config', namespace, config_data)

        with open('manifests/mutual-authentication.yaml', 'r') as ma_docs:

            for ma_doc in yaml.load_all(ma_docs):
                if ma_doc['kind'] == 'Service':

                    self.kube_client.create_service(ma_doc['metadata']['name'], namespace,
                                                    ma_doc['spec'])
                elif ma_doc['kind'] == 'Deployment':

                    if ma_doc['metadata']['name'] == "kerberos":

                        img = \
                            ma_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                                'latest', self.config.get_config_data('version'))

                        # ma_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(ma_doc['metadata']['name'], namespace,
                                                       ma_doc['spec'])
                else:
                    logger.error("Invalid document on Mutual Authetication manifest: %s" %
                                 ma_doc['kind'])

    # TODO: Minio configuration for Google Cloud
    # TODO: ACCESS keys as secrets
    def deploy_minio(self, namespace):
        with open('manifests/minio.yaml', 'r') as minio_docs:

            for minio_doc in yaml.load_all(minio_docs):
                if minio_doc['kind'] == 'Service':
                    self.kube_client.create_service(minio_doc['metadata']['name'],
                                                    namespace,
                                                    minio_doc['spec'])

                elif minio_doc['kind'] == 'Deployment':

                    self.kube_client.create_deployment(minio_doc['metadata']['name'],
                                                       namespace, minio_doc['spec'])

                elif minio_doc['kind'] == 'PersistentVolumeClaim':

                    self.kube_client.create_pvc(minio_doc['metadata']['name'],
                                                namespace, minio_doc['spec'])

                else:
                    logger.error("Invalid document on Minio manifest: %s" %
                                 minio_doc['kind'])

    # TODO: Access keys as secrets
    def deploy_image_manager(self, namespace):

        with open('manifests/image-manager.yaml', 'r') as image_manager_docs:

            for image_doc in yaml.load_all(image_manager_docs):
                if image_doc['kind'] == 'Service':
                    self.kube_client.create_service(image_doc['metadata']['name'],
                                                    namespace,
                                                    image_doc['spec'])

                elif image_doc['kind'] == 'Deployment':

                    img = \
                        image_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                            'latest', self.config.get_config_data('version'))

                    image_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(image_doc['metadata']['name'],
                                                       namespace, image_doc['spec'])

                else:
                    logger.error("Invalid document on Image Manager manifest: %s" %
                                 image_doc['kind'])

    def deploy_ejbca(self, namespace):

        with open('manifests/ejbca.yaml', 'r') as ejbca_docs:

            for ejbca_doc in yaml.load_all(ejbca_docs):
                if ejbca_doc['kind'] == 'Service':
                    self.kube_client.create_service(ejbca_doc['metadata']['name'],
                                                    namespace,
                                                    ejbca_doc['spec'])

                elif ejbca_doc['kind'] == 'Deployment':

                    img = \
                        ejbca_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                            'latest', self.config.get_config_data('version'))

                    ejbca_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(ejbca_doc['metadata']['name'],
                                                       namespace, ejbca_doc['spec'])

                elif ejbca_doc['kind'] == 'PersistentVolumeClaim':

                    self.kube_client.create_pvc(ejbca_doc['metadata']['name'],
                                                namespace, ejbca_doc['spec'])

                else:
                    logger.error("Invalid document on EJBCA manifest: %s" %
                                 ejbca_doc['kind'])

    def deploy_alarm_manager(self, namespace):

        # TODO: Mount the alarm metamodel files
        with open('manifests/alarm-manager.yaml', 'r') as alarm_manager_docs:

            for alarm_doc in yaml.load_all(alarm_manager_docs):
                if alarm_doc['kind'] == 'Service':
                    self.kube_client.create_service(alarm_doc['metadata']['name'],
                                                    namespace,
                                                    alarm_doc['spec'])

                elif alarm_doc['kind'] == 'Deployment':

                    img = \
                        alarm_doc['spec']['template']['spec']['containers'][0]['image'].replace(
                            'latest', self.config.get_config_data('version'))

                    alarm_doc['spec']['template']['spec']['containers'][0]['image'] = img

                    self.kube_client.create_deployment(alarm_doc['metadata']['name'],
                                                       namespace, alarm_doc['spec'])

                elif alarm_doc['kind'] == 'PersistentVolumeClaim':

                    self.kube_client.create_pvc(alarm_doc['metadata']['name'],
                                                namespace, alarm_doc['spec'])

                else:
                    logger.error("Invalid document on Alarm Manager manifest: %s" %
                                 alarm_doc['kind'])

    def deploy_services(self, namespace):

        services_config = self.config.get_config_data('services')
        # This class instantiate the multiple dojot services
        self.deploy_zookeeper(namespace, services_config['zookeeper'])
        self.deploy_postgres(namespace, services_config['postgres'])
        self.deploy_mongodb(namespace, services_config['mongodb'])
        self.deploy_kafka(namespace, services_config['kafka'])
        self.deploy_rabbitmq(namespace)
        self.deploy_minio(namespace)

        self.deploy_apigw(namespace)
        self.deploy_auth(namespace, services_config['auth'])
        self.deploy_mutual_auth(namespace)
        self.deploy_ejbca(namespace)

        self.deploy_device_manager(namespace)
        self.deploy_data_broker(namespace)
        self.deploy_history(namespace)
        self.deploy_alarm_manager(namespace)

        self.deploy_image_manager(namespace)

        self.deploy_mqtt_iotagent(namespace)
        self.deploy_flowbroker(namespace)

        self.deploy_gui(namespace)

    def deploy(self):
        logger.info("Starting deployment")

        namespace = self.config.get_config_data('namespace')

        self.kube_client.create_namespace(namespace)

        self.configure_storage(namespace)

        self.configure_external_access(namespace)

        self.deploy_services(namespace)

        logger.info("Dojot was successfully deployed!")
