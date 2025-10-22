from sqlalchemy import create_engine, delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
import subprocess
from datetime import datetime

DB_FILENAME = "key2play.sqlite"
CONNECTION_STRING = f"sqlite:///{DB_FILENAME}"
defaults = {
    "num_leds_on_strip": 200,
    "num_leds_per_meter": 160,
    "keys_calibrated": False,
    "reinitialize_network_on_boot": True,
    "is_hotspot_active": False,
    "color2x": "#0074DE", #blue-ish; https://htmlcolorcodes.com/
    "color1x": "#B100B5", #purple-ish
    "color1":  "#33BF00", #green-ish
    "color2":  "#F5EC00", #yellow-ish
    "color3":  "#B81D00", #red-ish
    "previewDepth": 1, #for use with the preview depth slider
}

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

    def backup_config_file_and_reset_to_factory(self):
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"key2play.{timestamp}.sqlite"
        _exitcode = subprocess.call(["mv", "key2play.sqlite", backup_filename])
        self.create_schema()

    def create_schema(self):
        engine = create_engine(CONNECTION_STRING)
        Base.metadata.create_all(engine)

    def get_sqlite_dump(self) -> str:
        return subprocess.check_output(["sqlite3", DB_FILENAME, ".dump"]).decode(
            "utf-8"
        )

    def get_config(self, key: str) -> str:
        engine = create_engine(CONNECTION_STRING)
        with Session(engine) as session:
            stmt = select(SimpleConfigKV).where(SimpleConfigKV.key == key)
            value = [kv.value for kv in session.scalars(stmt)]
            if value is not None and len(value) > 0:
                return value[0]
            elif key in defaults:
                return defaults[key]
            else:
                return None

    def set_config(self, key: str, value):
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
        return int(self.get_config("num_leds_on_strip"))

    def set_num_leds_on_strip(self, num: int):
        self.set_config("num_leds_on_strip", num)

    def num_leds_per_meter(self) -> int:
        return int(self.get_config("num_leds_per_meter"))

    def set_num_leds_per_meter(self, num: int):
        self.set_config("num_leds_per_meter", num)

    def keys_calibrated(self) -> bool:
        return bool(self.get_config("keys_calibrated"))

    def set_keys_calibrated(self, val: bool):
        self.set_config("keys_calibrated", val)

    def reinitialize_network_on_boot(self) -> bool:
        return bool(self.get_config("reinitialize_network_on_boot"))

    def set_reinitialize_network_on_boot(self, val: bool):
        self.set_config("reinitialize_network_on_boot", val)

    def is_hotspot_active(self) -> bool:
        return bool(self.get_config("is_hotspot_active"))

    def set_is_hotspot_active(self, val: bool):
        self.set_config("is_hotspot_active", val)
