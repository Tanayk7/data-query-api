from ariadne import QueryType, gql, make_executable_schema, ScalarType
from models import Trip, Vendor
from sqlalchemy.orm import Session
from flask import g
from datetime import datetime

# Define the GraphQL schema in SDL
type_defs = gql("""
    scalar DateTime

    type Trip {
        id: String
        vendor_id: Int
        pickup_datetime: DateTime
        dropoff_datetime: DateTime
        passenger_count: Int
        pickup_longitude: Float
        pickup_latitude: Float
        dropoff_longitude: Float
        dropoff_latitude: Float
        store_and_fwd_flag: String
        trip_duration: Int
        trip_distance: Float
    }

    type Vendor {
        id: Int
        vendor_id: Int
    }

    type Query {
        allTrips(limit: Int = 10, offset: Int = 0, vendor_id: Int, start_date: DateTime, end_date: DateTime): [Trip]
        tripById(id: String!): Trip
        allVendors(limit: Int = 10, offset: Int = 0): [Vendor]
        vendorById(id: Int!): Vendor
    }
""")

# Custom DateTime scalar
datetime_scalar = ScalarType("DateTime")

@datetime_scalar.serializer
def serialize_datetime(value):
    if isinstance(value, datetime):
        return value.isoformat()  # Convert datetime to ISO 8601 string
    raise ValueError("Expected a datetime object")

@datetime_scalar.value_parser
def parse_datetime(value):
    try:
        return datetime.fromisoformat(value)  # Parse ISO 8601 string to datetime
    except ValueError:
        raise ValueError("Invalid DateTime format. Expected ISO 8601 string.")

# Resolvers
query = QueryType()

@query.field("allTrips")
def resolve_all_trips(_, info, limit, offset, vendor_id=None, start_date=None, end_date=None):
    session: Session = g.db
    query = session.query(Trip)

    # Apply filters
    if vendor_id:
        query = query.filter(Trip.vendor_id == vendor_id)
    if start_date and end_date:
        query = query.filter(Trip.pickup_datetime.between(start_date, end_date))

    # Apply pagination
    return query.limit(limit).offset(offset).all()

@query.field("tripById")
def resolve_trip_by_id(_, info, id):
    session: Session = g.db
    return session.query(Trip).filter_by(id=id).first()

@query.field("allVendors")
def resolve_all_vendors(_, info, limit, offset):
    session: Session = g.db
    return session.query(Vendor).limit(limit).offset(offset).all()

@query.field("vendorById")
def resolve_vendor_by_id(_, info, id):
    session: Session = g.db
    return session.query(Vendor).filter_by(id=id).first()

# Create the executable schema
schema = make_executable_schema(type_defs, [query, datetime_scalar])
