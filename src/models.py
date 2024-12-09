from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey, CHAR
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

Base = declarative_base()

class Vendor(Base):
    __tablename__ = 'vendors'
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, unique=True, nullable=False)

class Trip(Base):
    __tablename__ = 'trips'
    id = Column(String, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    pickup_datetime = Column(DateTime)
    dropoff_datetime = Column(DateTime)
    passenger_count = Column(Integer)
    pickup_longitude = Column(Float)
    pickup_latitude = Column(Float)
    dropoff_longitude = Column(Float)
    dropoff_latitude = Column(Float)
    store_and_fwd_flag = Column(CHAR(1))
    trip_duration = Column(Integer)
    trip_distance = Column(Float)

    def to_dict(self):
        # Use a dictionary comprehension to exclude _sa_instance_state
        return {key: value for key, value in self.__dict__.items() if not key.startswith('_sa_')}

def initialize_indices(engine):
    with engine.connect() as connection:
        print("Creating indices...")
        # Index on pickup_datetime
        # - Speeds up queries filtering by time range (e.g., trips during a specific day/week/month).
        # - Useful for time-series analyses like peak hours or trends over time.
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_pickup_datetime ON trips (pickup_datetime);"))
        # Index on trip_distance
        # - Optimizes queries filtering or aggregating by trip distance (e.g., finding long/short trips).
        # - Useful for fare calculations, distance-based analyses, or detecting anomalies.
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_trip_distance ON trips (trip_distance);"))
        # Composite index on pickup_latitude and pickup_longitude
        # - Enhances performance for queries based on pickup locations (e.g., finding trips near a specific point or region).
        # - Useful for geospatial analyses without using PostGIS.
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_pickup_location ON trips (pickup_latitude, pickup_longitude);"))
        # Composite index on dropoff_latitude and dropoff_longitude
        # - Similar to the pickup location index but for dropoff coordinates.
        # - Useful for geospatial queries involving dropoff regions or clustering.
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_dropoff_location ON trips (dropoff_latitude, dropoff_longitude);"))
        # Index on vendor_id
        # - Speeds up queries filtering or grouping by vendor (e.g., analyzing vendor performance or trip counts).
        # - Useful for aggregations like total trips, average trip duration, or revenue per vendor.
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_vendor_id ON trips (vendor_id);"))
        print("Indices created successfully.")