"""User model."""

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, TimestampMixin, UUIDMixin
from app.utils.constants import CurrencyCode


class User(Base, UUIDMixin, TimestampMixin):
    """User account for authentication and portfolio ownership."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=CurrencyCode.USD.value
    )
    risk_free_rate: Mapped[float] = mapped_column(
        Numeric(6, 4), nullable=False, default=0.05
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
