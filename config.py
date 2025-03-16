from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert
from typing import List
from typing import Optional

DB_FILENAME = "key2play.sqlite"

DEFAULT_NUM_LEDS_ON_STRIP = 300


class Base(DeclarativeBase):
    pass


class SimpleConfigKV(Base):
    __tablename__ = "simple_config_kv"
    key: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    value: Mapped[str] = mapped_column()

    def __repr__(self) -> str:
        return f"SimpleConfigKV(key={self.key}, value={self.value}"


class Config:
    def get_config(self, key: str) -> str:
        engine = create_engine(f"sqlite:///{DB_FILENAME}")
        with Session(engine) as session:
            stmt = select(SimpleConfigKV).where(SimpleConfigKV.key == key)
            value = [kv.value for kv in session.scalars(stmt)]
            if value is not None and len(value) > 0:
                return value[0]
            else:
                return None

    def set_config(self, key: str, value: str):
        engine = create_engine(f"sqlite:///{DB_FILENAME}")
        with Session(engine) as session:
            stmt = (
                insert(SimpleConfigKV)
                .values(key=key, value=value)
                .on_conflict_do_update(index_elements=["key"], set_=dict(value=value))
            )
            session.execute(stmt)
            session.commit()

    def delete_config(key: str):
        engine = create_engine(f"sqlite:///{DB_FILENAME}")
        with Session(engine) as session:
            stmt = (
                delete(SimpleConfigKV)
                .values(
                    key=key,
                )
                .on_conflict_do_update(index_elements=["key"], set_=dict(value=value))
            )
            session.execute(stmt)
            session.commit()

    def num_leds_on_strip(self) -> int:
        num_leds_on_strip = self.get_config("num_leds_on_strip")
        if num_leds_on_strip is None:
            return DEFAULT_NUM_LEDS_ON_STRIP
        return num_leds_on_strip

    def set_num_leds_on_strip(self, num: int):
        self.set_config("num_leds_on_strip", num)


Base.metadata.create_all(create_engine(f"sqlite:///{DB_FILENAME}"))
appconfig = Config()
