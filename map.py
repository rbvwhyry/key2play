from sqlalchemy import create_engine, delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DB_FILENAME = "key2play.sqlite"
CONNECTION_STRING = f"sqlite:///{DB_FILENAME}"
# defaults = {"num_leds_on_strip": 200, "num_leds_per_meter": 160}


class Base(DeclarativeBase):
    pass


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
        self.create_schema()

    def create_schema(self):
        engine = create_engine(CONNECTION_STRING)
        Base.metadata.create_all(engine)

    # Insert or update a mapping
    def set_midi_led_map(
        self,
        midi_note: int,
        led_index: int,
        r: int,
        g: int,
        b: int,
        time_on: int,
        time_off: int,
    ):
        engine = create_engine(CONNECTION_STRING)
        with Session(engine) as session:
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

    # Get a mapping by midi_note
    def get_midi_led_map(self, midi_note: int) -> MidiLedMap | None:
        engine = create_engine(CONNECTION_STRING)
        with Session(engine) as session:
            stmt = select(MidiLedMap).where(MidiLedMap.midi_note == midi_note)
            result = session.scalar(stmt)
            return result

    # Delete a mapping by midi_note
    def delete_midi_led_map(self, midi_note: int):
        engine = create_engine(CONNECTION_STRING)
        with Session(engine) as session:
            stmt = delete(MidiLedMap).where(MidiLedMap.midi_note == midi_note)
            session.execute(stmt)
            session.commit()

    # Optional: get all mappings
    def get_all_midi_led_mappings(self) -> list[MidiLedMap]:
        engine = create_engine(CONNECTION_STRING)
        with Session(engine) as session:
            stmt = select(MidiLedMap)
            return list(session.scalars(stmt))
