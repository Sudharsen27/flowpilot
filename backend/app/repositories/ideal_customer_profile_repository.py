from sqlalchemy.orm import Session

from app.models.ideal_customer_profile import IdealCustomerProfile


class IdealCustomerProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_organization(self, organization_id: str) -> IdealCustomerProfile | None:
        return self.session.get(IdealCustomerProfile, organization_id)

    def save(self, organization_id: str, configuration: dict[str, object]) -> IdealCustomerProfile:
        profile = self.get_for_organization(organization_id)
        if profile is None:
            profile = IdealCustomerProfile(
                organization_id=organization_id,
                configuration=configuration,
            )
            self.session.add(profile)
        else:
            profile.configuration = configuration
        self.session.commit()
        self.session.refresh(profile)
        return profile