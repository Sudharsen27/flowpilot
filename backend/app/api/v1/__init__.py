from fastapi import APIRouter

from app.api.v1.agents import router as agents_router
from app.api.v1.auth import router as auth_router
from app.api.v1.follow_ups import router as follow_ups_router
from app.api.v1.leads import router as leads_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.sales_runs import agent_router as agent_sales_runs_router
from app.api.v1.sales_runs import lead_router as lead_sales_runs_router
from app.api.v1.sales_runs import org_router as org_sales_runs_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(organizations_router)
api_router.include_router(agents_router)
api_router.include_router(leads_router)
api_router.include_router(follow_ups_router)
api_router.include_router(agent_sales_runs_router)
api_router.include_router(lead_sales_runs_router)
api_router.include_router(org_sales_runs_router)
