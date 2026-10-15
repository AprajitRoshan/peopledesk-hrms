from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from app.database import Base

class InAppNotification(Base):
    __tablename__ = "in_app_notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(30), nullable=False, default="announcements", index=True)
    title = Column(String(180), nullable=False)
    message = Column(Text, nullable=False)
    source_type = Column(String(60), nullable=True)
    source_id = Column(String(80), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    leave_enabled = Column(Boolean, nullable=False, default=True)
    payroll_enabled = Column(Boolean, nullable=False, default=True)
    attendance_enabled = Column(Boolean, nullable=False, default=True)
    announcements_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
