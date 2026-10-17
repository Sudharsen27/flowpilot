from typing import Literal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.models.membership import MembershipRole
from app.repositories.ideal_customer_profile_repository import (
    IdealCustomerProfileRepository,
)
from app.schemas.ideal_customer_profile import (
    IdealCustomerProfilePublic,
    IdealCustomerProfileUpdate,
)

MANAGER_ROLES = frozenset({MembershipRole.OWNER, MembershipRole.ADMIN})
AvailableCriterion = Literal["company", "enquiry", "industry", "company_size", "geography"]
AVAILABLE_CRITERIA: list[AvailableCriterion] = [
    "company",
    "enquiry",
    "industry",
    "company_size",
    "geography",
]
PROFILE_UNAVAILABLE_CRITERIA = {
    "buyer_role": "Job title or buyer role is not available for deterministic scoring."
}


class IdealCustomerProfileService:
    def __init__(self, session: Session) -> None:
        self.profiles = IdealCustomerProfileRepository(session)

    def get(self, organization_id: str) -> IdealCustomerProfilePublic:
        row = self.profiles.get_for_organization(organization_id)
        configuration_valid = True
        try:
            configuration = IdealCustomerProfileUpdate.model_validate(
                row.configuration if row is not None else {}
            )
        except (ValidationError, TypeError, ValueError):
            configuration = IdealCustomerProfileUpdate()
            configuration_valid = False
        return IdealCustomerProfilePublic(
            **configuration.model_dump(),
            available_criteria=AVAILABLE_CRITERIA,
            unavailable_criteria=PROFILE_UNAVAILABLE_CRITERIA,
            configuration_valid=configuration_valid,
        )

    def update(
        self,
        *,
        organization_id: str,
        role: str,
        payload: IdealCustomerProfileUpdate,
    ) -> IdealCustomerProfilePublic:
        try:
            membership_role = MembershipRole(role)
        except ValueError as exc:
            raise ForbiddenError("Only owners and admins can change the ICP") from exc
        if membership_role not in MANAGER_ROLES:
            raise ForbiddenError("Only owners and admins can change the ICP")
        self.profiles.save(
            organization_id,
            payload.model_dump(mode="json"),
        )
        return IdealCustomerProfilePublic(
            **payload.model_dump(),
            available_criteria=AVAILABLE_CRITERIA,
            unavailable_criteria=PROFILE_UNAVAILABLE_CRITERIA,
            configuration_valid=True,
        )