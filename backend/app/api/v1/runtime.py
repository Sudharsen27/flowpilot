from fastapi import APIRouter, Depends

from app.api.deps import get_current_membership
from app.core.config import settings
from app.core.runtime_configuration import build_runtime_configuration
from app.models.membership import Membership
from app.schemas.runtime import RuntimeConfigurationPublic

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])


@router.get("/configuration", response_model=RuntimeConfigurationPublic)
def read_runtime_configuration(
    membership: Membership = Depends(get_current_membership),
) -> RuntimeConfigurationPublic:
    del membership
    return build_runtime_configuration(settings)
