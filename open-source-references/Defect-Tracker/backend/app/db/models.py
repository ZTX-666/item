from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, UniqueConstraint, String, Enum
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.domains.enums import IncidentSeverity, IncidentStatus


class Defect(Base):
    __tablename__ = 'defects'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reported_by = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    subcategory = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    absn = Column(Text, nullable=False)
    assigned_to = Column(Text, nullable=True)
    status = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(Text, nullable=True)

class DefectAuditLog(Base):
    __tablename__ = 'defect_audit_log'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    defect_id = Column(UUID(as_uuid=True), ForeignKey('defects.id'), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    changed_by = Column(Text, nullable=False)
    old_status = Column(Text, nullable=False)
    new_status = Column(Text, nullable=False)

class User(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)

class Role(Base):
    __tablename__ = 'roles'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False)

class UserRole(Base):
    __tablename__ = 'user_roles'
    __table_args__ = (UniqueConstraint('user_id', 'role_id', name='uix_user_role'),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=False)

class Scope(Base):
    __tablename__ = 'scopes'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False)

class RoleScope(Base):
    __tablename__ = 'role_scopes'
    __table_args__ = (UniqueConstraint('role_id', 'scope_id', name='uix_role_scope'),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=False)
    scope_id = Column(UUID(as_uuid=True), ForeignKey('scopes.id'), nullable=False)

class SafetyIncident(Base):
    __tablename__ = 'safety_incidents'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reported_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    severity = Column(Enum(IncidentSeverity), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String, nullable=False)
    department = Column(String, nullable=False)
    shift = Column(String, nullable=False)
    status = Column(Enum(IncidentStatus), nullable=False, default=IncidentStatus.OPEN)
    corrective_action = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class SafetyIncidentAuditLog(Base):
    __tablename__ = 'safety_incident_audit_logs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey('safety_incidents.id'), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable = False)
    old_status = Column(Enum(IncidentStatus), nullable=False)
    new_status = Column(Enum(IncidentStatus), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


    