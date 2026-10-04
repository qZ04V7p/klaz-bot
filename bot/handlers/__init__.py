from .common import router as common_router
from .worker import router as worker_router
from .admin  import router as admin_router
from .client import router as client_router

__all__ = ["common_router", "worker_router", "admin_router", "client_router"]
