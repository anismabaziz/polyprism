from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Market(Base):
    __tablename__ = "markets"

    market_id: Mapped[str] = mapped_column(String(66), primary_key=True)  # condition_id
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    resolution_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)  # YES/NO/PENDING
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class OrderBookSnapshot(Base):
    """
    TimescaleDB hypertable — partitioned by ts.
    Stores order book state at a point in time.

    NOTE: ``token_id`` keys a tradable outcome (e.g. YES/NO), not a market
    condition. Market identity (condition id) and token identity live in
    different domains; a dedicated token table is deferred.
    """

    __tablename__ = "orderbook_snapshots"

    token_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True, primary_key=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True, primary_key=True
    )
    bids: Mapped[list] = mapped_column(JSON, nullable=False)  # [{price, size}, ...]
    asks: Mapped[list] = mapped_column(JSON, nullable=False)  # [{price, size}, ...]
    best_bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_ask: Mapped[float | None] = mapped_column(Float, nullable=True)
