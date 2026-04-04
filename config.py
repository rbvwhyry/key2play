from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.dialects.sqlite import insert
from datetime import datetime
import subprocess

DB_FILENAME = "key2play.sqlite"
CONNECTION_STRING = f"sqlite:///{DB_FILENAME}"
defaults = {
    "num_leds_on_strip": 200,
    "num_leds_per_meter": 160,
    "keys_calibrated": False,
    "reinitialize_network_on_boot": True,
    "is_hotspot_active": False,
    "color2x": "#0074DE",  # blue-ish; https://htmlcolorcodes.com/
    "color1x": "#B100B5",  # purple-ish
    "color1": "#33BF00",  # green-ish
    "color2": "#F5EC00",  # yellow-ish
    "color3": "#CCCCCC",  # light-gray-ish
    "previewDepth": 1,  # for use with the preview depth slider
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
        self._engine = create_engine(
            CONNECTION_STRING
        )  # shared engine — created once, reused for all queries
        self._cache = {}  # in-memory cache for config values; invalidated on write
        with (
            Session(self._engine) as session
        ):  # enable WAL mode — allows reads to proceed concurrently during writes
            session.execute(text("PRAGMA journal_mode=WAL"))
            session.commit()
        self.create_schema()

    def backup_config_file_and_reset_to_factory(self):
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        backup_filename = f"key2play.{timestamp}.sqlite"
        _exitcode = subprocess.call(["mv", "key2play.sqlite", backup_filename])
        self._engine = create_engine(CONNECTION_STRING)  # new file — new engine
        self._cache = {}  # clear cache after reset
        self.create_schema()

    def create_schema(self):
        Base.metadata.create_all(self._engine)

    def get_sqlite_dump(self) -> str:
        return subprocess.check_output(["sqlite3", DB_FILENAME, ".dump"]).decode(
            "utf-8"
        )

    def get_config(self, key: str) -> str:
        if key in self._cache:  # return cached value instantly — no SQLite hit
            return self._cache[key]

        with Session(self._engine) as session:
            stmt = select(SimpleConfigKV).where(SimpleConfigKV.key == key)
            value = [kv.value for kv in session.scalars(stmt)]

            if value is not None and len(value) > 0:
                result = value[0]
            elif key in defaults:
                result = defaults[key]
            else:
                result = None

        self._cache[key] = result  # cache for next time

        return result

    def set_config(self, key: str, value):
        self._cache.pop(
            key, None
        )  # invalidate cache on write so next read gets fresh value

        with Session(self._engine) as session:
            stmt = (
                insert(SimpleConfigKV)
                .values(key=key, value=value)
                .on_conflict_do_update(index_elements=["key"], set_=dict(value=value))
            )
            session.execute(stmt)
            session.commit()

    def delete_config(self, key: str):
        self._cache.pop(key, None)  # invalidate cache on delete

        with Session(self._engine) as session:
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


class MidiLedMap(Base):
    __tablename__ = "midi_led_map"
    midi_note: Mapped[int] = mapped_column(primary_key=True)
    led_index: Mapped[int] = mapped_column()
    r: Mapped[int] = mapped_column()
    g: Mapped[int] = mapped_column()
    b: Mapped[int] = mapped_column()
    time_on: Mapped[int] = mapped_column()
    time_off: Mapped[int] = mapped_column()

    def __repr__(self) -> str:
        return (
            f"MidiLedMap("
            f"midi_note={self.midi_note}, "
            f"led_index={self.led_index}, "
            f"r={self.r}, "
            f"g={self.g}, "
            f"b={self.b}, "
            f"time_on='{self.time_on}', "
            f"time_off='{self.time_off}'"
            f")"
        )


class MidiToLedMapping:
    def __init__(self):
        self._engine = create_engine(
            CONNECTION_STRING
        )  # shared engine — created once, reused for all queries

    def set_midi_led_row(
        self,
        midi_note: int,
        led_index: int,
        r: int,
        g: int,
        b: int,
        time_on: int,
        time_off: int,
    ):
        with Session(self._engine) as session:
            stmt = (
                insert(MidiLedMap)
                .values(
                    midi_note=midi_note,
                    led_index=led_index,
                    r=r,
                    g=g,
                    b=b,
                    time_on=time_on,
                    time_off=time_off,
                )
                .on_conflict_do_update(
                    index_elements=["midi_note"],
                    set_={
                        "led_index": led_index,
                        "r": r,
                        "g": g,
                        "b": b,
                        "time_on": time_on,
                        "time_off": time_off,
                    },
                )
            )
            session.execute(stmt)
            session.commit()

    def get_midi_led_row(self, midi_note: int) -> MidiLedMap | None:
        with Session(self._engine) as session:
            stmt = select(MidiLedMap).where(MidiLedMap.midi_note == midi_note)
            result = session.scalar(stmt)

            return result

    def delete_midi_led_row(self, midi_note: int):
        with Session(self._engine) as session:
            stmt = delete(MidiLedMap).where(MidiLedMap.midi_note == midi_note)
            session.execute(stmt)
            session.commit()

    def get_midi_led_map(self) -> list[MidiLedMap]:
        with Session(self._engine) as session:
            stmt = select(MidiLedMap)

            return list(session.scalars(stmt))

    def delete_all_maps(self):
        with Session(self._engine) as session:
            stmt = delete(MidiLedMap)
            session.execute(stmt)
            session.commit()
