from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UtcDateTime(TypeDecorator[datetime]):
    """Store UTC datetimes and always read them back with a UTC offset."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, _dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(unique=True, index=True)
    task_id: Mapped[str] = mapped_column()
    model: Mapped[str] = mapped_column(index=True)
    final_status: Mapped[str] = mapped_column(index=True)
    agent_claimed_success: Mapped[bool] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime,
        default=lambda: datetime.now(UTC),
    )

    steps: Mapped[list["Step"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="Step.index",
    )


class Step(Base):
    __tablename__ = "steps"
    __table_args__ = (UniqueConstraint("run_id", "index", name="uq_steps_run_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    index: Mapped[int] = mapped_column()
    type: Mapped[str] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    file: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[str] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(nullable=True)
    tests_passed: Mapped[int | None] = mapped_column(nullable=True)
    tests_failed: Mapped[int | None] = mapped_column(nullable=True)
    error_signature: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(back_populates="steps")
