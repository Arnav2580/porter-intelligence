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


class IngestionStagingStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    FAILED = "failed"


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


class ShadowCase(Base):
    __tablename__ = "shadow_cases"

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
    source_channel = Column(String(50), nullable=False, index=True)
    live_write_suppressed = Column(Boolean, default=True, nullable=False)
    shadow_reason = Column(String(100), default="read_only_shadow")
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
        Index("ix_shadow_cases_driver_created", "driver_id", "created_at"),
        Index("ix_shadow_cases_tier_status", "tier", "status"),
        Index("ix_shadow_cases_source_created", "source_channel", "created_at"),
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


class IngestionStagingRecord(Base):
    __tablename__ = "ingestion_staging"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False, index=True)
    mapping_name = Column(String(100), nullable=False)
    external_trip_id = Column(String(100), index=True)
    payload = Column(JSONB, nullable=False)
    status = Column(
        SAEnum(IngestionStagingStatus),
        default=IngestionStagingStatus.PENDING,
        nullable=False,
        index=True,
    )
    retry_count = Column(Integer, default=0, nullable=False)
    stream_message_id = Column(String(100))
    error_message = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    queued_at = Column(DateTime(timezone=True))
    last_error_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_ingestion_staging_status_created", "status", "created_at"),
        Index("ix_ingestion_staging_source_status", "source", "status"),
    )
