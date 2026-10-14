from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from app.database import Base


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    recipient = Column(String(255), nullable=False, index=True)
    template_key = Column(String(80), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="logged")
    error_message = Column(Text, nullable=True)
    related_entity_type = Column(String(80), nullable=True)
    related_entity_id = Column(String(80), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
