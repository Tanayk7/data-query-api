import os
import boto3
from dotenv import load_dotenv
from flask import Flask, request, jsonify, g, send_from_directory
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session
from models import Base, Vendor, Trip, initialize_indices  # Assuming models are in a `models.py` file
from gql_schema import schema
from ariadne import graphql_sync
from gql_schema import schema
from ariadne.explorer import ExplorerGraphiQL
from flasgger import Swagger
from werkzeug.utils import secure_filename
from uuid import uuid4

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize Swagger
swagger = Swagger(app)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")  # Example: 'postgresql://user:password@localhost:5432/taxi_db'
engine = create_engine(DATABASE_URL)
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
print("DB engine and Session factory instance created successfully!")

# initialize_indices(engine)

# AWS Configuration
S3_BUCKET = os.getenv("AWS_S3_BUCKET_NAME")
SQS_QUEUE_URL = os.getenv("AWS_SQS_QUEUE_URL")

session = boto3.session.Session(
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
)

# Initialize AWS Clients
s3_client = session.client("s3",)
sqs_client = session.client("sqs")

@app.route("/graphql", methods=["GET"])
def graphql_explorer():
    explorer_html = ExplorerGraphiQL().html(None)
    return explorer_html, 200

# Serve the GraphQL API
@app.route("/graphql", methods=["POST"])
def graphql_server():
    data = request.get_json()
    success, result = graphql_sync(schema, data, context_value={"request": request})
    status_code = 200 if success else 400
    return jsonify(result), status_code

# Middleware for session management
@app.before_request
def create_session():
    g.db = SessionLocal()

@app.teardown_request
def close_session(exception=None):
    SessionLocal.remove()  # Properly removes the session

@app.route('/', methods=['GET'])
def home():
    """
    Home Route
    ---
    responses:
      200:
        description: Server is up and running
        content:
          application/json:
            schema:
              type: object
              properties:
                message:
                  type: string
    """
    print("Home route called!")
    return jsonify({"message": "Server is up and running"}), 200

@app.route('/trips', methods=['GET'])
def get_trips():
    """
    Retrieve trip data
    ---
    parameters:
      - name: start_date
        in: query
        type: string
        required: false
        description: Start date for filtering trips (ISO format)
      - name: end_date
        in: query
        type: string
        required: false
        description: End date for filtering trips (ISO format)
      - name: pickup_long
        in: query
        type: number
        required: false
        description: Pickup longitude
      - name: pickup_lat
        in: query
        type: number
        required: false
        description: Pickup latitude
    responses:
      200:
        description: A list of trips
        content:
          application/json:
            schema:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  vendor_id:
                    type: integer
                  pickup_datetime:
                    type: string
                  trip_distance:
                    type: number
    """
    try:
        # Retrieve query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        pickup_long = request.args.get('pickup_long')
        pickup_lat = request.args.get('pickup_lat')

        # Build the query
        query = g.db.query(Trip)
        if start_date and end_date:
            query = query.filter(Trip.pickup_datetime.between(start_date, end_date))
        if pickup_long:
            query = query.filter(Trip.pickup_longitude == float(pickup_long))
        if pickup_lat:
            query = query.filter(Trip.pickup_latitude == float(pickup_lat))

        # Execute the query
        trips = query.all()
        # Serialize the trips using the `to_dict` method
        trips_data = [trip.to_dict() for trip in trips]

        return jsonify(trips_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/trips/stats', methods=['GET'])
def get_trip_stats():
    """
    Retrieve aggregated trip statistics
    ---
    responses:
      200:
        description: Aggregated trip statistics
        content:
          application/json:
            schema:
              type: object
              properties:
                average_trip_duration:
                  type: number
                total_days:
                  type: integer
                trips_per_day:
                  type: array
                  items:
                    type: object
                    properties:
                      date:
                        type: string
                      total_trips:
                        type: integer
    """
    try:
        # Calculate average trip duration
        avg_duration = g.db.query(func.avg(Trip.trip_duration)).scalar()

        # Calculate total trips per day
        trips_per_day = g.db.query(
            func.date_trunc('day', Trip.pickup_datetime).label('day'),
            func.count(Trip.id).label('total_trips')
        ).group_by('day').all()

        # Calculate total number of distinct days
        total_days = g.db.query(func.count(func.distinct(func.date_trunc('day', Trip.pickup_datetime)))).scalar()
        
        # Format response
        stats = {
            'average_trip_duration': avg_duration,
            'total_days': total_days,
            'trips_per_day': [{'date': str(day), 'total_trips': total} for day, total in trips_per_day]
        }
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    """
    Upload a file to S3 and send a message to SQS
    ---
    tags:
      - File Upload
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: The file to upload
    responses:
      200:
        description: File uploaded and ETL job queued successfully!
        schema:
          type: object
          properties:
            message:
              type: string
              example: File uploaded and ETL job queued successfully!
            s3_key:
              type: string
              example: "6f9b7a5d_example.txt"
            sqs_message_id:
              type: string
              example: "df4b5e9b-3a2d-4e9f-8c9e-92d5df897123"
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
              example: No file part in the request
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: An error occurred during file upload
    """
    
    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    print("File: ", file)

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    try:
        # Generate a unique filename
        original_filename = secure_filename(file.filename)
        print("original_filename: ", original_filename)
        unique_filename = f"{uuid4()}_{original_filename}"
        print("unique_filename: ", unique_filename)

        print("Uploading file to s3...")
        # Upload file to S3
        s3_client.upload_fileobj(file, S3_BUCKET, unique_filename)
        print("Uploaded file to s3 successfully!")

        # Prepare the SQS message
        sqs_message = {
            "s3_key": unique_filename,
            "bucket_name": S3_BUCKET,
            'MessageGroupId': "ETL_JOB"
        }
        
        print("Sending message to sqs...")
        sqs_response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=jsonify(sqs_message).get_data(as_text=True),
            MessageGroupId="etl-job",
            MessageDeduplicationId= str(uuid4()),
        )
        print("sqs_response: ", sqs_response)

        return jsonify({
            "message": "File uploaded and ETL job queued successfully!",
            "s3_key": unique_filename,
            "sqs_message_id": sqs_response["MessageId"],
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/trigger_job", methods=["POST"])
def trigger_job():
    """
    Upload a file to S3 and send a message to SQS
    ---
    tags:
      - Trigger ETL job using s3 key
    consumes:
      - application/json
    parameters:
      - name: s3_key
        type: string
        required: true
        description: The s3 key of file to trigger ETL job 
    responses:
      200:
        description: ETL job triggered successfully and SQS message sent
        schema:
          type: object
          properties:
            message:
              type: string
              example: ETL job queued successfully!
            s3_key:
              type: string
              example: "6f9b7a5d_example.txt"
            sqs_message_id:
              type: string
              example: "df4b5e9b-3a2d-4e9f-8c9e-92d5df897123"
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
              example: An error occurred while triggering ETL job
    """
    data = request.json
    s3_key = data['s3_key']

    try:
        # Prepare the SQS message
        sqs_message = {
            "s3_key": s3_key,
            "bucket_name": S3_BUCKET,
            'MessageGroupId': "ETL_JOB"
        }
        
        print("Sending message to sqs...")
        sqs_response = sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=jsonify(sqs_message).get_data(as_text=True),
            MessageGroupId="etl-job",
            MessageDeduplicationId= str(uuid4()),
        )
        print("sqs_response: ", sqs_response)

        return jsonify({
            "message": "ETL job queued successfully!",
            "s3_key": s3_key,
            "sqs_message_id": sqs_response["MessageId"],
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
