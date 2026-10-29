from fastapi import APIRouter

from app.api.v1.activity import router as activity_router
from app.api.v1.agent_executions import router as agent_executions_router
from app.api.v1.agents import router as agents_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.auth import router as auth_router
from app.api.v1.company_prospects import router as company_prospects_router
from app.api.v1.contact import router as contact_router
from app.api.v1.deals import router as deals_router
from app.api.v1.follow_ups import router as follow_ups_router
from app.api.v1.inbox import router as inbox_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.leads import router as leads_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.prospect_discovery import router as prospect_discovery_router
from app.api.v1.public_enquiries import router as public_enquiries_router
from app.api.v1.runtime import router as runtime_router
from app.api.v1.sales_runs import agent_router as agent_sales_runs_router
from app.api.v1.sales_runs import lead_router as lead_sales_runs_router
from app.api.v1.sales_runs import org_router as org_sales_runs_router
from app.api.v1.sales_targets import router as sales_targets_router
from app.api.v1.users import router as users_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(organizations_router)
api_router.include_router(activity_router)
api_router.include_router(analytics_router)
api_router.include_router(knowledge_router)
api_router.include_router(inbox_router)
api_router.include_router(approvals_router)
api_router.include_router(public_enquiries_router)
api_router.include_router(contact_router)
api_router.include_router(company_prospects_router)
api_router.include_router(deals_router)
api_router.include_router(sales_targets_router)
api_router.include_router(runtime_router)
api_router.include_router(agents_router)
api_router.include_router(agent_executions_router)
api_router.include_router(leads_router)
api_router.include_router(prospect_discovery_router)
api_router.include_router(follow_ups_router)
api_router.include_router(agent_sales_runs_router)
api_router.include_router(lead_sales_runs_router)
api_router.include_router(org_sales_runs_router)
api_router.include_router(webhooks_router)
api_router.include_router(workflows_router)
api_router.include_router(integrations_router)
