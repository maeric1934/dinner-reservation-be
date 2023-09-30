from flask import Flask, redirect, request, jsonify
from flask_cors import CORS
import sqlite3
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Add CORS headers for allowed origins
def add_cors_headers(response):
    allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    origin = request.headers.get("Origin")
    if origin in allowed_origins:
        response.headers.add("Access-Control-Allow-Origin", origin)
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add('Access-Control-Allow-Methods', 'POST')
    response.headers.add('Access-Control-Allow-Methods', 'PUT')
    response.headers.add('Access-Control-Allow-Methods', 'DELETE')
    response.headers.add('Access-Control-Allow-Methods', 'GET')
    return response

app.after_request(add_cors_headers)

# Establish a database connection
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def home():
    return redirect('http://localhost:3000')

@app.route("/get-reservation-via-token", methods=['GET'])
def get_reservation():
    if request.method == 'GET':
        con = get_db_connection()
        cur = con.cursor()
        reservation_token = request.args.get('reservation_token', '')

        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query = 'SELECT reservation_first_name, reservation_last_name, reservation_datetime, phone_number, number_of_guests FROM reservations WHERE reservation_datetime >= ? AND reservation_token = ?'
        reservation = cur.execute(query, (current_datetime, reservation_token)).fetchone()
        con.close()

        if reservation:
            return jsonify(dict(reservation)), 200
        else:
            return jsonify({"error": "Reservation not found"}), 404

# API endpoint for adding a reservation
@app.route("/add-reservation", methods=['POST'])
def add_reservation():
    if request.method == 'POST':
        con = get_db_connection()
        cur = con.cursor()
        data = request.get_json()

        is_valid, error_messages = validate_reservation_data(data)
        if not is_valid:
            return jsonify({"errors": error_messages}), 422

        try:
            # Generate unique id to be used in update or delete
            unique_id = str(uuid.uuid4())
            # Insert into the database
            cur.execute(
                """
                    INSERT INTO reservations (
                        reservation_first_name, 
                        reservation_last_name, 
                        reservation_datetime,
                        phone_number, 
                        number_of_guests,
                        reservation_token
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        data['reservation_first_name'],
                        data['reservation_last_name'],
                        data['reservation_datetime'],
                        data['phone_number'],
                        data['number_of_guests'],
                        unique_id
                    ))
            con.commit()
            msg = unique_id
        except:
            con.rollback()
            msg = "Error in the INSERT"
            return jsonify({"errors": msg}), 422
        finally:
            con.close()
            return jsonify(msg), 200

@app.route("/delete-reservation/<int:id>", methods=["DELETE"])
def delete_reservation(id):
    con = get_db_connection()
    cur = con.cursor()

    is_valid, error_messages = validate_update_delete_reservation(id)
    if not is_valid:
        return jsonify({"errors": error_messages}), 422
    try:
        cur.execute("DELETE FROM reservations WHERE id = ?", (id,))
        con.commit()
        return jsonify({"message": "Reservation deleted successfully"}), 200
    except:
        con.rollback()
        return jsonify({"error": "Error deleting reservation"}), 500
    finally:
        con.close()

@app.route("/update-reservation/<int:id>", methods=['PUT'])
def update_reservation(id):
    if request.method == 'PUT':
        con = get_db_connection()
        cur = con.cursor()
        data = request.get_json()

        is_valid, error_messages = validate_update_delete_reservation(id)
        if not is_valid:
            return jsonify({"errors": error_messages}), 422

        is_valid, error_messages = validate_reservation_data(data)
        if not is_valid:
            return jsonify({"errors": error_messages}), 422

        # Assuming your table is named 'reservations'
        cur.execute("""
            UPDATE reservations
            SET reservation_first_name = ?,
                reservation_last_name = ?,
                reservation_datetime = ?,
                phone_number = ?,
                number_of_guests = ?
            WHERE id = ?
        """, (data['reservation_first_name'],
              data['reservation_last_name'],
              data['reservation_datetime'],
              data['phone_number'],
              data['number_of_guests'],
              id))

        con.commit()
        con.close()
        return jsonify({"message": "Reservation updated successfully"}), 200

# API endpoint for getting a reservation from today onwards  
@app.route("/reservations", methods=['GET'])
def reservations():
    if request.method == 'GET':
        con = get_db_connection()
        cur = con.cursor()
        current_datetime = datetime.now().strftime('%Y-%m-%d') + '00:00'
        rows = cur.execute('SELECT reservation_first_name, reservation_last_name, reservation_datetime, number_of_guests FROM reservations WHERE reservation_datetime >= ?', (current_datetime,)).fetchall()
        reservations = [dict(row) for row in rows]
        con.close()
        return jsonify(reservations), 200
        
        
# Validation logic for reservation data
def validate_reservation_data(data):
    required_fields = ['reservation_first_name', 'reservation_last_name', 'reservation_datetime', 'phone_number', 'number_of_guests']
    errors = []

    for field in required_fields:
        if field not in data or data[field] == "":
            errors.append(f"Field '{field}' is required")
    
    # Validate number of guests
    number_of_guests = int(data.get('number_of_guests', 0))
    if number_of_guests < 1 or number_of_guests > 5:
        errors.append("Number of guests should be between 1 and 5")

    # Validate reservation datetime format
    if 'reservation_datetime' in data:
        try:
            reservation_datetime = datetime.strptime(data['reservation_datetime'], '%Y-%m-%d %H:%M')
            reservation_time = reservation_datetime.time()
            
             # Validate reservation datetime format and time range
            if reservation_time < datetime.strptime('18:00', '%H:%M').time() or reservation_time > datetime.strptime('21:30', '%H:%M').time():
                errors.append("Reservation time should be between 6:00 PM and 9:30 PM")
        

            # Validate time reservation divisible by 30 mins
            if reservation_time.minute % 30 != 0:
                errors.append("Reservation time should be divisible by 30 minutes (e.g., 6:00 PM, 6:30 PM, etc.)")

            # Validate reservation date is at least 2 days in advance
            current_date = datetime.now().date()
            reservation_date = reservation_datetime.date()
            if reservation_date <= current_date + timedelta(days=1):
                errors.append("Reservation date should be at least 2 days in advance")

            # Calculate the start and end of the 30-minute interval for the given reservation datetime
            con = get_db_connection()
            cur = con.cursor()
            interval_end = reservation_datetime + timedelta(minutes=30)

            # Count reservations within this interval
            count = cur.execute('SELECT COUNT(*) FROM reservations WHERE reservation_datetime >= ? AND reservation_datetime < ?', 
                                (reservation_datetime.strftime('%Y-%m-%d %H:%M'), interval_end.strftime('%Y-%m-%d %H:%M'))).fetchone()[0]
            if count >= 3:
                errors.append("There can only be 3 reservations made per 30 minutes.")

        except ValueError:
            errors.append("Invalid datetime format. Use YYYY-MM-DD HH:MM")
    
    return len(errors) == 0, errors
    
def validate_update_delete_reservation(id):
    con = get_db_connection()
    cur = con.cursor()
    errors = []

    # Fetch the existing reservation datetime for the given ID
    cur.execute("SELECT reservation_datetime FROM reservations WHERE id = ?", (id,))
    existing_datetime = cur.fetchone()

    if existing_datetime is None:
        errors.append("Reservation not found")
    
    existing_datetime = datetime.strptime(existing_datetime['reservation_datetime'], '%Y-%m-%d %H:%M')

    # Check if the update is allowed (Not within 2 days before old reservation date)
    if existing_datetime.date() <= datetime.now().date() + timedelta(days=1):
        errors.append("Reservation to be updated must not be within two days from now")
    
    return len(errors) == 0, errors

##### Api Routes ######

if __name__ == "__main__":
    app.run(debug=True)