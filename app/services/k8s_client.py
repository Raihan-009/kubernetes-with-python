from kubernetes import client, config
from typing import Optional, Dict, Any
import concurrent.futures

class K8sClient:
    def __init__(self):
        try:
            config.load_kube_config()
        except:
            config.load_incluster_config()
        
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.batch_v1 = client.BatchV1Api()
        self.custom_objects = client.CustomObjectsApi()
        
    def get_resource_metrics(self, namespace: str, resource_type: str, resource_name: str) -> Dict[str, Any]:
        """Get resource metrics for a specific resource"""
        try:
            metrics = self.custom_objects.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural=resource_type
            )
            
            for item in metrics['items']:
                if item['metadata']['name'] == resource_name:
                    return {
                        'cpu': item['containers'][0]['usage']['cpu'],
                        'memory': item['containers'][0]['usage']['memory']
                    }
            return {'cpu': 'N/A', 'memory': 'N/A'}
        except:
            return {'cpu': 'N/A', 'memory': 'N/A'}

    def get_cluster_resources(self) -> Dict[str, list]:
        """Get all resources across the cluster with their status and metrics"""
        try:
            # Get all namespaces first
            namespace_list = self.core_v1.list_namespace()
            namespaces = [ns.metadata.name for ns in namespace_list.items]
            
            resources = {
                "nodes": [],
                "namespaces": [],
                "deployments": [],
                "statefulsets": [],
                "daemonsets": [],
                "pods": [],
                "services": [],
                "ingresses": [],
                "persistentvolumes": [],
                "persistentvolumeclaims": [],
                "configmaps": [],
                "secrets": [],
                "jobs": [],
                "cronjobs": []
            }

            # Add namespace information
            for ns in namespace_list.items:
                resources["namespaces"].append({
                    "kind": "Namespace",
                    "name": ns.metadata.name,
                    "status": ns.status.phase,
                    "creation_timestamp": ns.metadata.creation_timestamp
                })

            # Get node information
            nodes = self.core_v1.list_node()
            for node in nodes.items:
                conditions = {cond.type: cond.status for cond in node.status.conditions}
                resources["nodes"].append({
                    "kind": "Node",
                    "name": node.metadata.name,
                    "status": "Ready" if conditions.get("Ready") == "True" else "NotReady",
                    "cpu_capacity": node.status.capacity.get('cpu'),
                    "memory_capacity": node.status.capacity.get('memory'),
                    "pods_capacity": node.status.capacity.get('pods'),
                    "kubernetes_version": node.status.node_info.kubelet_version
                })

            # Get resources from all namespaces
            for namespace in namespaces:
                try:
                    # Get metrics for all pods in the namespace
                    pod_metrics = {}
                    try:
                        metrics_list = self.custom_objects.list_namespaced_custom_object(
                            group="metrics.k8s.io",
                            version="v1beta1",
                            namespace=namespace,
                            plural="pods"
                        )
                        
                        for metric in metrics_list.get('items', []):
                            pod_name = metric['metadata']['name']
                            containers = metric.get('containers', [])
                            total_cpu = 0
                            total_memory = 0
                            
                            for container in containers:
                                cpu = container.get('usage', {}).get('cpu', '0')
                                memory = container.get('usage', {}).get('memory', '0')
                                
                                # Convert CPU to millicores if in n format
                                if cpu.endswith('n'):
                                    cpu = int(cpu[:-1]) / 1000000
                                elif cpu.endswith('m'):
                                    cpu = int(cpu[:-1])
                                
                                # Convert memory to Mi
                                if memory.endswith('Ki'):
                                    memory = int(memory[:-2]) / 1024
                                elif memory.endswith('Mi'):
                                    memory = int(memory[:-2])
                                elif memory.endswith('Gi'):
                                    memory = int(memory[:-2]) * 1024
                                
                                total_cpu += cpu
                                total_memory += memory
                                
                            pod_metrics[pod_name] = {
                                'cpu': f"{total_cpu}m",
                                'memory': f"{total_memory}Mi"
                            }
                    except Exception as e:
                        print(f"Error getting metrics for namespace {namespace}: {str(e)}")
                        pod_metrics = {}

                    # Get deployments
                    deployments = self.apps_v1.list_namespaced_deployment(namespace)
                    for dep in deployments.items:
                        resources["deployments"].append({
                            "kind": "Deployment",
                            "name": dep.metadata.name,
                            "namespace": namespace,
                            "desired_replicas": dep.spec.replicas,
                            "available_replicas": dep.status.available_replicas or 0,
                            "status": "Healthy" if (dep.status.available_replicas or 0) == dep.spec.replicas else "Unhealthy",
                            "containers": [
                                {
                                    "name": container.name,
                                    "image": container.image
                                }
                                for container in dep.spec.template.spec.containers
                            ]
                        })

                    # Get pods
                    pods = self.core_v1.list_namespaced_pod(namespace)
                    for pod in pods.items:
                        metrics = pod_metrics.get(pod.metadata.name, {'cpu': 'N/A', 'memory': 'N/A'})
                        resources["pods"].append({
                            "kind": "Pod",
                            "name": pod.metadata.name,
                            "namespace": namespace,
                            "status": pod.status.phase,
                            "cpu_usage": metrics['cpu'],
                            "memory_usage": metrics['memory'],
                            "node": pod.spec.node_name,
                            "ip": pod.status.pod_ip,
                            "start_time": pod.status.start_time,
                            "containers": [
                                {
                                    "name": cont.name,
                                    "ready": cont.ready,
                                    "restart_count": cont.restart_count,
                                    "image": cont.image
                                }
                                for cont in pod.status.container_statuses
                            ] if pod.status.container_statuses else []
                        })

                    # Get services
                    services = self.core_v1.list_namespaced_service(namespace)
                    for svc in services.items:
                        resources["services"].append({
                            "kind": "Service",
                            "name": svc.metadata.name,
                            "namespace": namespace,
                            "type": svc.spec.type,
                            "cluster_ip": svc.spec.cluster_ip,
                            "ports": [f"{port.port}:{port.target_port}" for port in svc.spec.ports]
                        })

                    # Get StatefulSets
                    statefulsets = self.apps_v1.list_namespaced_stateful_set(namespace)
                    for sts in statefulsets.items:
                        resources["statefulsets"].append({
                            "kind": "StatefulSet",
                            "name": sts.metadata.name,
                            "namespace": namespace,
                            "desired_replicas": sts.spec.replicas,
                            "current_replicas": sts.status.current_replicas or 0,
                            "status": "Healthy" if (sts.status.current_replicas or 0) == sts.spec.replicas else "Unhealthy"
                        })

                    # Get DaemonSets
                    daemonsets = self.apps_v1.list_namespaced_daemon_set(namespace)
                    for ds in daemonsets.items:
                        resources["daemonsets"].append({
                            "kind": "DaemonSet",
                            "name": ds.metadata.name,
                            "namespace": namespace,
                            "desired_number": ds.status.desired_number_scheduled,
                            "current_number": ds.status.current_number_scheduled,
                            "status": "Healthy" if ds.status.number_ready == ds.status.desired_number_scheduled else "Unhealthy"
                        })

                    # Get Jobs
                    jobs = self.batch_v1.list_namespaced_job(namespace)
                    for job in jobs.items:
                        resources["jobs"].append({
                            "kind": "Job",
                            "name": job.metadata.name,
                            "namespace": namespace,
                            "status": job.status.conditions[-1].type if job.status.conditions else "Unknown",
                            "start_time": job.status.start_time,
                            "completion_time": job.status.completion_time
                        })

                    # Get ConfigMaps
                    configmaps = self.core_v1.list_namespaced_config_map(namespace)
                    resources["configmaps"].extend([
                        {
                            "kind": "ConfigMap",
                            "name": cm.metadata.name,
                            "namespace": namespace
                        }
                        for cm in configmaps.items
                    ])

                    # Get Secrets
                    secrets = self.core_v1.list_namespaced_secret(namespace)
                    resources["secrets"].extend([
                        {
                            "kind": "Secret",
                            "name": secret.metadata.name,
                            "namespace": namespace,
                            "type": secret.type
                        }
                        for secret in secrets.items
                    ])

                    # Get Ingresses
                    try:
                        networking_v1 = client.NetworkingV1Api()
                        ingresses = networking_v1.list_namespaced_ingress(namespace)
                        resources["ingresses"].extend([
                            {
                                "kind": "Ingress",
                                "name": ing.metadata.name,
                                "namespace": namespace,
                                "hosts": [rule.host for rule in ing.spec.rules] if ing.spec.rules else []
                            }
                            for ing in ingresses.items
                        ])
                    except Exception as e:
                        print(f"Error getting ingresses for namespace {namespace}: {str(e)}")

                except Exception as e:
                    print(f"Error processing namespace {namespace}: {str(e)}")
                    continue

            return resources
        except Exception as e:
            raise Exception(f"Error getting cluster resources: {str(e)}")

    def get_pods(self, namespace: str = "default"):
        return self.core_v1.list_namespaced_pod(namespace=namespace)

    def get_pod_logs(self, pod_name: str, namespace: str = "default", container: Optional[str] = None):
        return self.core_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container
        )

    def get_pod_events(self, pod_name: str, namespace: str = "default"):
        field_selector = f'involvedObject.name={pod_name}'
        return self.core_v1.list_namespaced_event(
            namespace=namespace,
            field_selector=field_selector
        )

    def get_deployments(self, namespace: str = "default"):
        return self.apps_v1.list_namespaced_deployment(namespace=namespace)

    def get_jobs(self, namespace: str = "default"):
        return self.batch_v1.list_namespaced_job(namespace=namespace)

    def get_namespaces(self):
        """Get all namespaces in the cluster"""
        return self.core_v1.list_namespace()

    def get_namespace_resources(self, namespace: str):
        """Get all resources in a specific namespace"""
        return {
            "pods": self.get_pods(namespace),
            "services": self.core_v1.list_namespaced_service(namespace),
            "deployments": self.get_deployments(namespace),
            "jobs": self.get_jobs(namespace),
            "configmaps": self.core_v1.list_namespaced_config_map(namespace),
            "secrets": self.core_v1.list_namespaced_secret(namespace),
            "ingresses": client.NetworkingV1Api().list_namespaced_ingress(namespace),
            "statefulsets": self.apps_v1.list_namespaced_stateful_set(namespace)
        }

    def get_services(self, namespace: str = "default"):
        """Get all services in a namespace"""
        try:
            return self.core_v1.list_namespaced_service(namespace=namespace)
        except Exception as e:
            print(f"Error getting services: {str(e)}")
            raise e 

    def get_workload_resources(self) -> Dict[str, list]:
        """Get all workload resources with their metrics"""
        try:
            resources = []
            
            # Get all namespaces
            namespaces = [ns.metadata.name for ns in self.core_v1.list_namespace().items]
            
            for namespace in namespaces:
                try:
                    # Get metrics for all pods in the namespace
                    pod_metrics = {}
                    try:
                        metrics_list = self.custom_objects.list_namespaced_custom_object(
                            group="metrics.k8s.io",
                            version="v1beta1",
                            namespace=namespace,
                            plural="pods"
                        )
                        
                        for metric in metrics_list.get('items', []):
                            pod_name = metric['metadata']['name']
                            containers = metric.get('containers', [])
                            total_cpu = 0
                            total_memory = 0
                            
                            for container in containers:
                                cpu = container.get('usage', {}).get('cpu', '0')
                                memory = container.get('usage', {}).get('memory', '0')
                                
                                # Convert CPU to millicores
                                if cpu.endswith('n'):
                                    cpu = int(cpu[:-1]) / 1000000
                                elif cpu.endswith('m'):
                                    cpu = int(cpu[:-1])
                                
                                # Convert memory to Mi
                                if memory.endswith('Ki'):
                                    memory = int(memory[:-2]) / 1024
                                elif memory.endswith('Mi'):
                                    memory = int(memory[:-2])
                                elif memory.endswith('Gi'):
                                    memory = int(memory[:-2]) * 1024
                                
                                total_cpu += cpu
                                total_memory += memory
                                
                            pod_metrics[pod_name] = {
                                'cpu': f"{total_cpu}m",
                                'memory': f"{total_memory}Mi"
                            }
                    except Exception as e:
                        print(f"Error getting metrics for namespace {namespace}: {str(e)}")
                        pod_metrics = {}

                    # Get deployments
                    deployments = self.apps_v1.list_namespaced_deployment(namespace)
                    for dep in deployments.items:
                        total_cpu = 0
                        total_memory = 0
                        dep_pods = self.core_v1.list_namespaced_pod(
                            namespace=namespace,
                            label_selector=','.join(f'{k}={v}' for k, v in (dep.spec.selector.match_labels or {}).items())
                        )
                        
                        for pod in dep_pods.items:
                            metrics = pod_metrics.get(pod.metadata.name, {'cpu': '0m', 'memory': '0Mi'})
                            total_cpu += float(metrics['cpu'].rstrip('m'))
                            total_memory += float(metrics['memory'].rstrip('Mi'))
                        
                        resources.append({
                            "kind": "Deployment",
                            "name": dep.metadata.name,
                            "namespace": namespace,
                            "cluster": self.get_cluster_name(),
                            "status": "Healthy" if (dep.status.available_replicas or 0) == dep.spec.replicas else "Unhealthy",
                            "pods_count": {
                                "desired": dep.spec.replicas,
                                "available": dep.status.available_replicas or 0
                            },
                            "last_change": dep.metadata.creation_timestamp,
                            "version": dep.metadata.resource_version,
                            "cpu_usage": f"{total_cpu}m",
                            "memory_usage": f"{total_memory}Mi"
                        })

                    # Get StatefulSets
                    statefulsets = self.apps_v1.list_namespaced_stateful_set(namespace)
                    for sts in statefulsets.items:
                        total_cpu = 0
                        total_memory = 0
                        sts_pods = self.core_v1.list_namespaced_pod(
                            namespace=namespace,
                            label_selector=','.join(f'{k}={v}' for k, v in (sts.spec.selector.match_labels or {}).items())
                        )
                        
                        for pod in sts_pods.items:
                            metrics = pod_metrics.get(pod.metadata.name, {'cpu': '0m', 'memory': '0Mi'})
                            total_cpu += float(metrics['cpu'].rstrip('m'))
                            total_memory += float(metrics['memory'].rstrip('Mi'))
                        
                        resources.append({
                            "kind": "StatefulSet",
                            "name": sts.metadata.name,
                            "namespace": namespace,
                            "cluster": self.get_cluster_name(),
                            "status": "Healthy" if (sts.status.ready_replicas or 0) == sts.spec.replicas else "Unhealthy",
                            "pods_count": {
                                "desired": sts.spec.replicas,
                                "available": sts.status.ready_replicas or 0
                            },
                            "last_change": sts.metadata.creation_timestamp,
                            "version": sts.metadata.resource_version,
                            "cpu_usage": f"{total_cpu}m",
                            "memory_usage": f"{total_memory}Mi"
                        })

                    # Get DaemonSets
                    daemonsets = self.apps_v1.list_namespaced_daemon_set(namespace)
                    for ds in daemonsets.items:
                        total_cpu = 0
                        total_memory = 0
                        ds_pods = self.core_v1.list_namespaced_pod(
                            namespace=namespace,
                            label_selector=','.join(f'{k}={v}' for k, v in (ds.spec.selector.match_labels or {}).items())
                        )
                        
                        for pod in ds_pods.items:
                            metrics = pod_metrics.get(pod.metadata.name, {'cpu': '0m', 'memory': '0Mi'})
                            total_cpu += float(metrics['cpu'].rstrip('m'))
                            total_memory += float(metrics['memory'].rstrip('Mi'))
                        
                        resources.append({
                            "kind": "DaemonSet",
                            "name": ds.metadata.name,
                            "namespace": namespace,
                            "cluster": self.get_cluster_name(),
                            "status": "Healthy" if ds.status.number_ready == ds.status.desired_number_scheduled else "Unhealthy",
                            "pods_count": {
                                "desired": ds.status.desired_number_scheduled,
                                "available": ds.status.number_ready
                            },
                            "last_change": ds.metadata.creation_timestamp,
                            "version": ds.metadata.resource_version,
                            "cpu_usage": f"{total_cpu}m",
                            "memory_usage": f"{total_memory}Mi"
                        })

                    # Get standalone pods (pods not managed by any controller)
                    pods = self.core_v1.list_namespaced_pod(namespace)
                    for pod in pods.items:
                        if not pod.metadata.owner_references:  # Standalone pod
                            metrics = pod_metrics.get(pod.metadata.name, {'cpu': '0m', 'memory': '0Mi'})
                            resources.append({
                                "kind": "Pod",
                                "name": pod.metadata.name,
                                "namespace": namespace,
                                "cluster": self.get_cluster_name(),
                                "status": pod.status.phase,
                                "pods_count": {
                                    "desired": 1,
                                    "available": 1 if pod.status.phase == "Running" else 0
                                },
                                "last_change": pod.metadata.creation_timestamp,
                                "version": pod.metadata.resource_version,
                                "cpu_usage": metrics['cpu'],
                                "memory_usage": metrics['memory']
                            })

                except Exception as e:
                    print(f"Error processing namespace {namespace}: {str(e)}")
                    continue

            return {
                "resources": sorted(resources, key=lambda x: (x['namespace'], x['kind'], x['name'])),
                "summary": {
                    "total_resources": len(resources),
                    "by_kind": {
                        kind: len([r for r in resources if r['kind'] == kind])
                        for kind in ["Deployment", "StatefulSet", "DaemonSet", "Pod"]
                    },
                    "by_namespace": {
                        namespace: len([r for r in resources if r['namespace'] == namespace])
                        for namespace in set(r['namespace'] for r in resources)
                    }
                }
            }

        except Exception as e:
            raise Exception(f"Error getting workload resources: {str(e)}")

    def get_cluster_name(self) -> str:
        """Get the cluster name from current context"""
        try:
            _, active_context = config.list_kube_config_contexts()
            return active_context['name']
        except:
            return "unknown-cluster" 