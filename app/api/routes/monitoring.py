from fastapi import APIRouter, HTTPException, Body
from app.services.k8s_client import K8sClient
from typing import Dict, List, Any, Optional
import datetime
from kubernetes.client import (
    V1Pod, V1ObjectMeta, V1PodSpec, V1Container, V1Namespace,
    V1Deployment, V1DeploymentSpec, V1LabelSelector, V1Service,
    V1ServiceSpec, V1ServicePort
)

router = APIRouter()
k8s_client = K8sClient()

@router.get("/health", summary="Get unhealthy pods and resources across cluster")
async def get_unhealthy_resources():
    """
    Get all currently unhealthy resources including:
    - Failed/Pending pods
    - Container errors (CrashLoopBackOff, ImagePullBackOff, etc.)
    - Resource constraints (CPU/Memory)
    - Volume issues (binding, attachment)
    - Unavailable deployments/statefulsets/daemonsets
    """
    try:
        # Get all namespaces
        namespaces = k8s_client.core_v1.list_namespace()
        unhealthy_resources = {
            "unhealthy_pods": [],
            "unhealthy_deployments": [],
            "unhealthy_statefulsets": [],
            "unhealthy_daemonsets": [],
            "unhealthy_pvcs": [],  # Added for volume issues
            "resource_pressure": [],  # Added for node resource pressure
            "total_unhealthy_resources": 0
        }

        # Check nodes for resource pressure
        nodes = k8s_client.core_v1.list_node()
        for node in nodes.items:
            node_pressures = []
            for condition in node.status.conditions:
                if condition.type in ["MemoryPressure", "DiskPressure", "PIDPressure", "CPUPressure"] and condition.status == "True":
                    node_pressures.append({
                        "type": condition.type,
                        "message": condition.message
                    })
            
            if node_pressures:
                unhealthy_resources["resource_pressure"].append({
                    "node": node.metadata.name,
                    "pressures": node_pressures
                })

        for ns in namespaces.items:
            namespace = ns.metadata.name

            # Check PVCs for binding/attachment issues
            pvcs = k8s_client.core_v1.list_namespaced_persistent_volume_claim(namespace)
            for pvc in pvcs.items:
                if pvc.status.phase != "Bound":
                    events = k8s_client.core_v1.list_namespaced_event(
                        namespace=namespace,
                        field_selector=f'involvedObject.name={pvc.metadata.name}'
                    )
                    unhealthy_resources["unhealthy_pvcs"].append({
                        "name": pvc.metadata.name,
                        "namespace": namespace,
                        "phase": pvc.status.phase,
                        "events": [
                            {
                                "type": event.type,
                                "reason": event.reason,
                                "message": event.message,
                                "count": event.count,
                                "last_timestamp": event.last_timestamp
                            }
                            for event in events.items
                            if event.type == "Warning"
                        ]
                    })

            # Check pods with enhanced error detection
            pods = k8s_client.core_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                # Extended list of container error states to check
                container_error_reasons = [
                    "CrashLoopBackOff",
                    "Error",
                    "CreateContainerError",
                    "ImagePullBackOff",
                    "ErrImagePull",
                    "ContainerCreating",
                    "PodInitializing",
                    "Init:Error",
                    "Init:CrashLoopBackOff"
                ]

                # Check if pod is unhealthy
                is_unhealthy = (
                    pod.status.phase in ["Failed", "Pending"] or
                    any(
                        (container.state.waiting and 
                         container.state.waiting.reason in container_error_reasons) or
                        (container.state.terminated and 
                         container.state.terminated.exit_code != 0)
                        for container in (pod.status.container_statuses or [])
                    )
                )

                if is_unhealthy:
                    events = k8s_client.core_v1.list_namespaced_event(
                        namespace=namespace,
                        field_selector=f'involvedObject.name={pod.metadata.name}'
                    )

                    # Get detailed error reasons
                    error_reasons = []
                    resource_issues = []
                    
                    if pod.status.container_statuses:
                        for container in pod.status.container_statuses:
                            if container.state.waiting:
                                error_reasons.append(f"{container.name}: {container.state.waiting.reason} - {container.state.waiting.message}")
                            elif container.state.terminated and container.state.terminated.exit_code != 0:
                                error_reasons.append(f"{container.name}: Terminated with exit code {container.state.terminated.exit_code}")

                    # Check events for resource issues
                    for event in events.items:
                        if event.reason in ["FailedScheduling", "OutOfmemory", "OOMKilling"]:
                            resource_issues.append({
                                "type": event.reason,
                                "message": event.message
                            })

                    unhealthy_resources["unhealthy_pods"].append({
                        "name": pod.metadata.name,
                        "namespace": namespace,
                        "status": pod.status.phase,
                        "node": pod.spec.node_name,
                        "error_reasons": error_reasons,
                        "resource_issues": resource_issues,
                        "events": [
                            {
                                "type": event.type,
                                "reason": event.reason,
                                "message": event.message,
                                "count": event.count,
                                "last_timestamp": event.last_timestamp
                            }
                            for event in events.items
                            if event.type == "Warning"
                        ]
                    })

            # Check deployments
            deployments = k8s_client.apps_v1.list_namespaced_deployment(namespace)
            for dep in deployments.items:
                if (dep.status.available_replicas or 0) < dep.spec.replicas:
                    unhealthy_resources["unhealthy_deployments"].append({
                        "name": dep.metadata.name,
                        "namespace": namespace,
                        "desired_replicas": dep.spec.replicas,
                        "available_replicas": dep.status.available_replicas or 0,
                        "conditions": [
                            {
                                "type": condition.type,
                                "status": condition.status,
                                "reason": condition.reason,
                                "message": condition.message
                            }
                            for condition in dep.status.conditions
                            if condition.status == "False"  # Only include failed conditions
                        ]
                    })

            # Check StatefulSets
            statefulsets = k8s_client.apps_v1.list_namespaced_stateful_set(namespace)
            for sts in statefulsets.items:
                if (sts.status.ready_replicas or 0) < sts.spec.replicas:
                    unhealthy_resources["unhealthy_statefulsets"].append({
                        "name": sts.metadata.name,
                        "namespace": namespace,
                        "desired_replicas": sts.spec.replicas,
                        "ready_replicas": sts.status.ready_replicas or 0
                    })

            # Check DaemonSets
            daemonsets = k8s_client.apps_v1.list_namespaced_daemon_set(namespace)
            for ds in daemonsets.items:
                if ds.status.number_ready < ds.status.desired_number_scheduled:
                    unhealthy_resources["unhealthy_daemonsets"].append({
                        "name": ds.metadata.name,
                        "namespace": namespace,
                        "desired_pods": ds.status.desired_number_scheduled,
                        "ready_pods": ds.status.number_ready
                    })

        # Update total count to include new categories
        total_unhealthy = (
            len(unhealthy_resources["unhealthy_pods"]) +
            len(unhealthy_resources["unhealthy_deployments"]) +
            len(unhealthy_resources["unhealthy_statefulsets"]) +
            len(unhealthy_resources["unhealthy_daemonsets"]) +
            len(unhealthy_resources["unhealthy_pvcs"]) +
            len(unhealthy_resources["resource_pressure"])
        )
        unhealthy_resources["total_unhealthy_resources"] = total_unhealthy

        # Enhanced summary
        unhealthy_resources["summary"] = {
            "total_unhealthy_resources": total_unhealthy,
            "by_type": {
                "pods": len(unhealthy_resources["unhealthy_pods"]),
                "deployments": len(unhealthy_resources["unhealthy_deployments"]),
                "statefulsets": len(unhealthy_resources["unhealthy_statefulsets"]),
                "daemonsets": len(unhealthy_resources["unhealthy_daemonsets"]),
                "pvcs": len(unhealthy_resources["unhealthy_pvcs"]),
                "nodes_with_resource_pressure": len(unhealthy_resources["resource_pressure"])
            },
            "error_categories": {
                "container_errors": len([pod for pod in unhealthy_resources["unhealthy_pods"] 
                                      if any("ImagePullBackOff" in reason or "CrashLoopBackOff" in reason 
                                           for reason in pod["error_reasons"])]),
                "resource_constraints": len([pod for pod in unhealthy_resources["unhealthy_pods"] 
                                          if pod["resource_issues"]]),
                "volume_issues": len(unhealthy_resources["unhealthy_pvcs"]),
                "node_pressure": len(unhealthy_resources["resource_pressure"])
            },
            "affected_namespaces": len(set(
                item["namespace"] for category in ["unhealthy_pods", "unhealthy_deployments", 
                                                 "unhealthy_statefulsets", "unhealthy_daemonsets", 
                                                 "unhealthy_pvcs"]
                for item in unhealthy_resources[category]
            ))
        }

        return unhealthy_resources

    except Exception as e:
        print(f"Error in get_unhealthy_resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/kubectl/command", summary="Execute kubectl command string")
async def execute_kubectl_string(
    command: str = Body(..., description="kubectl command string", 
    example="kubectl create deployment nginx --image=nginx --replicas=3 -n default")
):
    """
    Execute kubectl commands as string input
    
    Examples:
    - kubectl create namespace test-ns
    - kubectl delete namespace test-ns
    - kubectl run nginx --image=nginx -n default
    - kubectl create deployment nginx --image=nginx --replicas=3
    - kubectl delete deployment nginx -n default
    - kubectl get pods -n default
    - kubectl get ns
    - kubectl create service nodeport nginx --tcp=80:80 --node-port=30080
    """
    try:
        # Parse command string
        parts = command.split()
        
        # Validate kubectl prefix
        if parts[0].lower() != "kubectl":
            raise HTTPException(
                status_code=400,
                detail="Command must start with 'kubectl'"
            )
        
        # Remove 'kubectl' from parts
        parts = parts[1:]
        
        if len(parts) < 2:
            raise HTTPException(
                status_code=400,
                detail="Invalid command format. Minimum format: kubectl <action> <resource_type/name> [flags]"
            )

        # Extract basic components
        action = parts[0]

        # Handle 'run' command differently as it has a different format
        if action == "run":
            if len(parts) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="Pod name is required for 'run' command"
                )

            # For 'run' command, the second part is the pod name
            args = {
                "name": parts[1],  # Second part is the pod name for 'run' command
                "namespace": "default",
                "image": None,
                "replicas": None,
                "ports": [],
                "labels": {},
                "node_port": None
            }

            # Parse remaining arguments
            i = 2
            while i < len(parts):
                if parts[i].startswith("--"):
                    flag = parts[i][2:]  # Remove '--' prefix
                    if "=" in flag:
                        # Handle --flag=value format
                        flag_name, value = flag.split("=", 1)
                        args[flag_name.replace("-", "_")] = value
                        i += 1
                    elif i + 1 < len(parts):
                        # Handle --flag value format
                        flag_name = flag
                        value = parts[i + 1]
                        args[flag_name.replace("-", "_")] = value
                        i += 2
                    else:
                        i += 1
                elif parts[i] == "-n" and i + 1 < len(parts):
                    args["namespace"] = parts[i + 1]
                    i += 2
                else:
                    i += 1

            if not args["image"]:
                raise HTTPException(
                    status_code=400,
                    detail="--image is required for 'run' command"
                )

            pod = V1Pod(
                metadata=V1ObjectMeta(
                    name=args["name"],
                    namespace=args["namespace"]
                ),
                spec=V1PodSpec(
                    containers=[
                        V1Container(
                            name=args["name"],
                            image=args["image"]
                        )
                    ]
                )
            )

            result = k8s_client.core_v1.create_namespaced_pod(
                namespace=args["namespace"],
                body=pod
            )

            return {
                "status": "success",
                "message": f"Pod {args['name']} created successfully",
                "details": {
                    "name": result.metadata.name,
                    "namespace": result.metadata.namespace,
                    "status": result.status.phase if result.status else "Unknown"
                }
            }

        # For other commands, continue with the existing logic
        resource_type = parts[1]

        # Parse common flags and arguments for other commands
        args = {
            "name": None,
            "namespace": "default",
            "image": None,
            "replicas": None,
            "ports": [],
            "labels": {},
            "node_port": None
        }

        # Parse remaining arguments for other commands
        i = 2
        while i < len(parts):
            if parts[i].startswith("--"):
                flag = parts[i][2:]  # Remove '--' prefix
                if "=" in flag:
                    # Handle --flag=value format
                    flag_name, value = flag.split("=", 1)
                    args[flag_name.replace("-", "_")] = value
                    i += 1
                elif i + 1 < len(parts):
                    # Handle --flag value format
                    flag_name = flag
                    value = parts[i + 1]
                    args[flag_name.replace("-", "_")] = value
                    i += 2
                else:
                    i += 1
            elif parts[i] == "-n" and i + 1 < len(parts):
                args["namespace"] = parts[i + 1]
                i += 2
            else:
                if not args["name"]:
                    args["name"] = parts[i]
                i += 1

        # Handle different resource types and actions
        if resource_type == "namespace":
            if action == "create":
                result = k8s_client.core_v1.create_namespace(
                    body=V1Namespace(
                        metadata=V1ObjectMeta(
                            name=args["name"]
                        )
                    )
                )
                return {
                    "status": "success",
                    "message": f"Namespace {args['name']} created successfully"
                }

            elif action == "delete":
                k8s_client.core_v1.delete_namespace(name=args["name"])
                return {
                    "status": "success",
                    "message": f"Namespace {args['name']} deleted successfully"
                }

            elif action == "get":
                if not args["name"]:
                    # List all namespaces
                    result = k8s_client.core_v1.list_namespace()
                    return {
                        "status": "success",
                        "namespaces": [
                            {
                                "name": ns.metadata.name,
                                "status": ns.status.phase,
                                "age": ns.metadata.creation_timestamp
                            }
                            for ns in result.items
                        ]
                    }
                else:
                    # Get specific namespace
                    result = k8s_client.core_v1.read_namespace(name=args["name"])
                    return {
                        "status": "success",
                        "details": {
                            "name": result.metadata.name,
                            "status": result.status.phase,
                            "age": result.metadata.creation_timestamp
                        }
                    }

        # Handle pod operations
        elif resource_type in ["pod", "pods", "po"]:
            if action == "delete":
                k8s_client.core_v1.delete_namespaced_pod(
                    name=args["name"],
                    namespace=args["namespace"]
                )
                return {
                    "status": "success",
                    "message": f"Pod {args['name']} deleted successfully"
                }
            
            elif action == "get":
                if not args["name"]:
                    # List all pods in namespace
                    pods = k8s_client.core_v1.list_namespaced_pod(namespace=args["namespace"])
                    return {
                        "status": "success",
                        "pods": [
                            {
                                "name": pod.metadata.name,
                                "namespace": pod.metadata.namespace,
                                "status": pod.status.phase,
                                "node": pod.spec.node_name
                            }
                            for pod in pods.items
                        ]
                    }
                else:
                    # Get specific pod
                    pod = k8s_client.core_v1.read_namespaced_pod(
                        name=args["name"],
                        namespace=args["namespace"]
                    )
                    return {
                        "status": "success",
                        "details": {
                            "name": pod.metadata.name,
                            "namespace": pod.metadata.namespace,
                            "status": pod.status.phase,
                            "node": pod.spec.node_name
                        }
                    }

        # Handle deployment operations
        elif resource_type in ["deployment", "deploy"]:
            if action == "create":
                if not args["image"]:
                    raise HTTPException(
                        status_code=400,
                        detail="--image is required for deployment creation"
                    )

                deployment = V1Deployment(
                    metadata=V1ObjectMeta(
                        name=args["name"],
                        namespace=args["namespace"]
                    ),
                    spec=V1DeploymentSpec(
                        replicas=int(args["replicas"]) if args["replicas"] else 1,
                        selector=V1LabelSelector(
                            match_labels={"app": args["name"]}
                        ),
                        template={
                            "metadata": {
                                "labels": {"app": args["name"]}
                            },
                            "spec": {
                                "containers": [{
                                    "name": args["name"],
                                    "image": args["image"]
                                }]
                            }
                        }
                    )
                )

                result = k8s_client.apps_v1.create_namespaced_deployment(
                    namespace=args["namespace"],
                    body=deployment
                )

                return {
                    "status": "success",
                    "message": f"Deployment {args['name']} created successfully",
                    "details": {
                        "name": result.metadata.name,
                        "namespace": result.metadata.namespace,
                        "replicas": result.spec.replicas
                    }
                }

            elif action == "delete":
                k8s_client.apps_v1.delete_namespaced_deployment(
                    name=args["name"],
                    namespace=args["namespace"]
                )
                return {
                    "status": "success",
                    "message": f"Deployment {args['name']} deleted successfully"
                }

        # Add more resource types and actions as needed

        raise HTTPException(
            status_code=501,
            detail=f"Command not implemented yet: {command}"
        )

    except Exception as e:
        error_message = str(e)
        if "already exists" in error_message.lower():
            raise HTTPException(
                status_code=409,
                detail=f"Resource already exists"
            )
        elif "not found" in error_message.lower():
            raise HTTPException(
                status_code=404,
                detail=f"Resource not found"
            )
        else:
            print(f"Error in execute_kubectl_command: {error_message}")
            raise HTTPException(status_code=500, detail=error_message) 