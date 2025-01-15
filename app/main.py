from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import pods, deployments, jobs, namespaces, cluster, services, monitoring

app = FastAPI(
    title="Kubernetes API",
    description="API for interacting with Kubernetes cluster",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cluster.router, prefix="/api/cluster", tags=["Cluster"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoring"])
app.include_router(namespaces.router, prefix="/api/namespaces", tags=["Namespaces"])
app.include_router(services.router, prefix="/api/services", tags=["Services"])
app.include_router(pods.router, prefix="/api/pods", tags=["Pods"])
app.include_router(deployments.router, prefix="/api/deployments", tags=["Deployments"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])

@app.get("/", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 