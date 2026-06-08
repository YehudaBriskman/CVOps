import uuid
from typing import Any, Optional

from sqlalchemy import Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base, EntityBase


class Org(Base, EntityBase):
    __tablename__ = "orgs"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<Org id={self.id} name={self.name!r}>"


class User(Base, EntityBase):
    __tablename__ = "users"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class Membership(Base, EntityBase):
    __tablename__ = "memberships"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_memberships_org_user"),)

    def __repr__(self) -> str:
        return f"<Membership id={self.id} org={self.org_id} user={self.user_id} role={self.role!r}>"
