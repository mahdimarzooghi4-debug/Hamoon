from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hamoon.domains.provider.domain.entities import (
    CapacityStatus,
    EligibilityOperator,
    MatchEligibility,
    ProviderStatus,
)
from hamoon.infrastructure.db.base import Base


class ProviderModel(Base):
    __tablename__ = "provider"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    status: Mapped[ProviderStatus] = mapped_column(
        Enum(ProviderStatus, name="provider_status"),
        nullable=False,
    )
    organization_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    integration_mode: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderServiceModel(Base):
    __tablename__ = "provider_service"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    supported_intervention_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    eligibility_policy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    coverage_policy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    coverage_fact_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    coverage_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sla_policy_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ProviderServiceEligibilityRuleModel(Base):
    __tablename__ = "provider_service_eligibility_rule"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_service_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_service.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fact_type: Mapped[str] = mapped_column(String(150), nullable=False)
    operator: Mapped[EligibilityOperator] = mapped_column(
        Enum(EligibilityOperator, name="provider_eligibility_operator"),
        nullable=False,
    )
    expected_value: Mapped[object | None] = mapped_column(JSON, nullable=True)
    reason_code: Mapped[str] = mapped_column(String(150), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ProviderCapacitySnapshotModel(Base):
    __tablename__ = "provider_capacity_snapshot"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_service_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_service.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capacity_status: Mapped[CapacityStatus] = mapped_column(
        Enum(CapacityStatus, name="provider_capacity_status"),
        nullable=False,
    )
    available_slots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ProviderMatchModel(Base):
    __tablename__ = "provider_match"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intervention_id: Mapped[UUID] = mapped_column(
        ForeignKey("intervention.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_type: Mapped[str] = mapped_column(String(150), nullable=False)
    household_context_version: Mapped[int] = mapped_column(Integer, nullable=False)
    matching_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )


class ProviderMatchCandidateModel(Base):
    __tablename__ = "provider_match_candidate"
    __table_args__ = (
        UniqueConstraint(
            "provider_match_id",
            "provider_service_id",
            name="uq_provider_match_candidate_service",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_match.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_service_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_service.id", ondelete="RESTRICT"),
        nullable=False,
    )
    eligibility: Mapped[MatchEligibility] = mapped_column(
        Enum(MatchEligibility, name="provider_match_eligibility"),
        nullable=False,
    )
    capacity_status: Mapped[CapacityStatus] = mapped_column(
        Enum(CapacityStatus, name="provider_capacity_status"),
        nullable=False,
    )
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class ProviderSelectionModel(Base):
    __tablename__ = "provider_selection"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_match.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    intervention_id: Mapped[UUID] = mapped_column(
        ForeignKey("intervention.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_service_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_service.id", ondelete="RESTRICT"),
        nullable=False,
    )
    human_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("human_decision.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    selected_by: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
    )
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)



class ProviderIdentityModel(Base):
    __tablename__ = "provider_identity"
    __table_args__ = (
        UniqueConstraint(
            "issuer",
            "external_identity_subject",
            name="uq_provider_identity_issuer_subject",
        ),
        UniqueConstraint("actor_id", name="uq_provider_identity_actor"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("actor.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    external_identity_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
