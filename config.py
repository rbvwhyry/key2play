from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from typing import List
from typing import Optional

DB_FILENAME = "key2play.sqlite"


class Base(DeclarativeBase):
    pass


class SimpleConfigKV(Base):
    __tablename__ = "simple_config_kv"
    key: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    value: Mapped[str] = mapped_column()

    def __repr__(self) -> str:
        return f"SimpleConfigKV(key={self.key}, value={self.value}"


class Config:
    def get_config(key: str) -> str:
        engine = create_engine(f"sqlite:///{DB_FILENAME}")
        with Session(engine) as session:
            stmt = select(SimpleConfigKV).where(SimpleConfigKV.key == key)
            value = [kv.value for kv in session.scalars(stmt)]
            return value[0]


    def set_config(key: str, value: str):
        engine = create_engine(f"sqlite:///{DB_FILENAME}")
        with Session(engine) as session:
            stmt = (
                insert(SimpleConfigKV)
                .values(key=key, value=value)
                .on_conflict_do_update(index_elements=["key"], set_=dict(value=value))
            )
            print(stmt)
            session.execute(stmt)
            session.commit()


Base.metadata.create_all(create_engine(f"sqlite:///{DB_FILENAME}"))
Config.set_config("test", "this is a test")
print(Config.get_config("test"))
