from fastapi import APIRouter, HTTPException
from app.services.k8s_client import K8sClient
from typing import Dict, List, Any
import datetime

router = APIRouter()
k8s_client = K8sClient()

@router.get("/health", summary="Get unhealthy pods across cluster")
async def get_unhealthy_resources():
    """
    Get all currently unhealthy resources (Failed/Pending pods, unavailable deployments, etc.)
    """
    try:
        # Get all namespaces
        namespaces = k8s_client.core_v1.list_namespace()
        unhealthy_resources = {
            "unhealthy_pods": [],
            "unhealthy_deployments": [],
            "unhealthy_statefulsets": [],
            "unhealthy_daemonsets": [],
            "total_unhealthy_resources": 0
        }

        for ns in namespaces.items:
            namespace = ns.metadata.name

            # Check pods - only include currently unhealthy ones
            pods = k8s_client.core_v1.list_namespaced_pod(namespace)
            for pod in pods.items:
                # Check if pod is currently unhealthy
                is_unhealthy = (
                    pod.status.phase in ["Failed", "Pending"] or 
                    any(
                        container.state.waiting and 
                        container.state.waiting.reason in ["CrashLoopBackOff", "Error", "CreateContainerError", "ImagePullBackOff"]
                        for container in (pod.status.container_statuses or [])
                    )
                )

                if is_unhealthy:
                    # Get only recent and relevant events
                    events = k8s_client.core_v1.list_namespaced_event(
                        namespace=namespace,
                        field_selector=f'involvedObject.name={pod.metadata.name}'
                    )

                    # Get current error reasons from container statuses
                    error_reasons = []
                    if pod.status.container_statuses:
                        for container in pod.status.container_statuses:
                            if container.state.waiting:
                                error_reasons.append(f"{container.name}: {container.state.waiting.reason} - {container.state.waiting.message}")
                            elif container.state.terminated and container.state.terminated.exit_code != 0:
                                error_reasons.append(f"{container.name}: Terminated with exit code {container.state.terminated.exit_code}")

                    unhealthy_resources["unhealthy_pods"].append({
                        "name": pod.metadata.name,
                        "namespace": namespace,
                        "status": pod.status.phase,
                        "node": pod.spec.node_name,
                        "error_reasons": error_reasons,
                        "events": [
                            {
                                "type": event.type,
                                "reason": event.reason,
                                "message": event.message,
                                "count": event.count,
                                "last_timestamp": event.last_timestamp
                            }
                            for event in events.items
                            if event.type == "Warning"  # Only include warning events
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

        # Update total count
        total_unhealthy = (
            len(unhealthy_resources["unhealthy_pods"]) +
            len(unhealthy_resources["unhealthy_deployments"]) +
            len(unhealthy_resources["unhealthy_statefulsets"]) +
            len(unhealthy_resources["unhealthy_daemonsets"])
        )
        unhealthy_resources["total_unhealthy_resources"] = total_unhealthy

        # Add summary
        unhealthy_resources["summary"] = {
            "total_unhealthy_resources": total_unhealthy,
            "by_type": {
                "pods": len(unhealthy_resources["unhealthy_pods"]),
                "deployments": len(unhealthy_resources["unhealthy_deployments"]),
                "statefulsets": len(unhealthy_resources["unhealthy_statefulsets"]),
                "daemonsets": len(unhealthy_resources["unhealthy_daemonsets"])
            },
            "affected_namespaces": len(set(
                pod["namespace"] for pod in unhealthy_resources["unhealthy_pods"]
            ) | set(
                dep["namespace"] for dep in unhealthy_resources["unhealthy_deployments"]
            ) | set(
                sts["namespace"] for sts in unhealthy_resources["unhealthy_statefulsets"]
            ) | set(
                ds["namespace"] for ds in unhealthy_resources["unhealthy_daemonsets"]
            ))
        }

        return unhealthy_resources

    except Exception as e:
        print(f"Error in get_unhealthy_resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 