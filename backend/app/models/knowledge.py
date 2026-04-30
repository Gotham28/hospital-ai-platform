from sqlalchemy import Column, Integer, Text, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db.base_class import Base

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospital.id"), nullable=False)
    content = Column(Text, nullable=False)

    # "fact" = hospital info/rules/FAQs; "instruction" = AI behaviour directive
    entry_type = Column(String(20), nullable=False, server_default="fact")

    # Vector column: 1536 dimensions for OpenAI's text-embedding-3-small
    embedding = Column(Vector(1536))

    created_at = Column(DateTime(timezone=True), server_default=func.now())