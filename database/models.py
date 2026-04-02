"""SQLAlchemy ORM models.

All operational entities for Porter Intelligence Platform.
"""

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class FraudCaseStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    CONFIRMED = "confirmed_fraud"
    FALSE_ALARM = "false_alarm"
    ESCALATED = "escalated"


class DriverActionType(str, enum.Enum):
    SUSPEND = "suspend"
    FLAG_REVIEW = "flag_review"
    MONITOR = "monitor"
    CLEAR = "clear"
    WATCHLIST = "watchlist"


class FraudCase(Base):
    __tablename__ = "fraud_cases"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    trip_id = Column(String(100), nullable=False, index=True)
    driver_id = Column(String(100), nullable=False, index=True)
    zone_id = Column(String(50), index=True)
    fraud_type = Column(String(50))
    tier = Column(String(20), nullable=False)
    fraud_probability = Column(Float, nullable=False)
    top_signals = Column(JSONB)
    fare_inr = Column(Float)
    recoverable_inr = Column(Float)
    status = Column(
        SAEnum(FraudCaseStatus),
        default=FraudCaseStatus.OPEN,
        nullable=False,
    )
    assigned_to = Column(String(100))
    analyst_notes = Column(Text)
    override_reason = Column(Text)
    auto_escalated = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )
    resolved_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_fraud_cases_driver_created", "driver_id", "created_at"),
        Index("ix_fraud_cases_tier_status", "tier", "status"),
        Index("ix_fraud_cases_zone_created", "zone_id", "created_at"),
    )


class DriverAction(Base):
    __tablename__ = "driver_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver_id = Column(String(100), nullable=False, index=True)
    action_type = Column(SAEnum(DriverActionType), nullable=False)
    reason = Column(Text)
    performed_by = Column(String(100))
    case_id = Column(String(100))
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), index=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(100))
    resource_id = Column(String(100))
    details = Column(JSONB)
    ip_address = Column(String(50))
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class ModelMetrics(Base):
    __tablename__ = "model_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version = Column(String(50))
    eval_date = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    precision_action = Column(Float)
    recall = Column(Float)
    fpr = Column(Float)
    fraud_caught = Column(Integer)
    total_trips = Column(Integer)
    net_rec_per_trip = Column(Float)
    data_source = Column(String(50))
    notes = Column(Text)
