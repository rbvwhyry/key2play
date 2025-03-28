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
CONNECTION_STRING = f"sqlite:///{DB_FILENAME}"
DEFAULT_NUM_LEDS_ON_STRIP: int = 300
DEFAULT_NUM_LEDS_PER_METER: int = 160


class Base(DeclarativeBase):
    pass


class SimpleConfigKV(Base):
    __tablename__ = "simple_config_kv"
    key: Mapped[str] = mapped_column(primary_key=True, nullable=False)
    value: Mapped[str] = mapped_column()

    def __repr__(self) -> str:
        return f"SimpleConfigKV(key={self.key}, value={self.value}"


class Config:
    def __init__(self):
        self.create_schema()

    def create_schema(self):
        engine = create_engine(CONNECTION_STRING)
        Base.metadata.create_all(engine)

    def get_config(self, key: str) -> str:
        engine = create_engine(CONNECTION_STRING)
        with Session(engine) as session:
            stmt = select(SimpleConfigKV).where(SimpleConfigKV.key == key)
            value = [kv.value for kv in session.scalars(stmt)]
            if value is not None and len(value) > 0:
                return value[0]
            else:
                return None

    def set_config(self, key: str, value: str):
        engine = create_engine(CONNECTION_STRING)
        with Session(engine) as session:
            stmt = (
                insert(SimpleConfigKV)
                .values(key=key, value=value)
                .on_conflict_do_update(index_elements=["key"], set_=dict(value=value))
            )
            session.execute(stmt)
            session.commit()

    def delete_config(self, key: str):
        engine = create_engine(CONNECTION_STRING)
        with Session(engine) as session:
            stmt = delete(SimpleConfigKV).where(SimpleConfigKV.key == key)
            session.execute(stmt)
            session.commit()

    def num_leds_on_strip(self) -> int:
        num_leds_on_strip = self.get_config("num_leds_on_strip")
        if num_leds_on_strip is None:
            return int(DEFAULT_NUM_LEDS_ON_STRIP)
        return int(num_leds_on_strip)

    def set_num_leds_on_strip(self, num: int):
        self.set_config("num_leds_on_strip", num)

    def num_leds_per_meter(self) -> int:
        num_leds_per_meter = self.get_config("num_leds_per_meter")
        if num_leds_per_meter is None:
            return int(DEFAULT_NUM_LEDS_PER_METER)
        return int(num_leds_per_meter)

    def set_num_leds_per_meter(self, num: int):
        self.set_config("num_leds_per_meter", num)
