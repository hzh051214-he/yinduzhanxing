"""SQLAlchemy 数据模型。"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Reading(Base):
    """一次排盘请求。"""
    __tablename__ = "readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 出生信息
    birth_year   = Column(Integer, nullable=False)
    birth_month  = Column(Integer, nullable=False)
    birth_day    = Column(Integer, nullable=False)
    birth_hour   = Column(Integer, nullable=False)
    birth_minute = Column(Integer, nullable=False)
    lat          = Column(Float,   nullable=False)
    lon          = Column(Float,   nullable=False)
    tz_str       = Column(String(64), nullable=False, default="Asia/Shanghai")
    place_name   = Column(String(128))
    gender       = Column(String(4))
    relationship = Column(String(32), default="未知")
    time_precision_level = Column(Integer, default=2)  # 1-4
    name         = Column(String(64), default="")
    lang         = Column(String(4),  default="cn")
    modules      = Column(Text, default="core")  # 逗号分隔: core,career,love

    # D60 知情同意
    d60_consent  = Column(Boolean, default=None)

    # 任务状态
    status       = Column(String(16), default="pending")
    # pending → calculating → formatting → pdf → done | failed
    progress     = Column(Integer, default=0)   # 0-100
    error_msg    = Column(Text)

    # 关联报告
    report_id    = Column(UUID(as_uuid=True))

    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Report(Base):
    """生成好的报告文件。"""
    __tablename__ = "reports"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reading_id   = Column(UUID(as_uuid=True), nullable=False)
    html_path    = Column(String(256))   # 相对于 storage_path 的路径
    pdf_path     = Column(String(256))
    structured_md_path = Column(String(256))
    lagna        = Column(String(32))    # 上升星座（供封面显示）
    modules      = Column(Text)          # 实际生成的模块列表

    created_at   = Column(DateTime, default=datetime.utcnow)
    # 报告在多少秒后过期（初期 48 小时 = 172800 秒）
    expires_in   = Column(Integer, default=172800)
