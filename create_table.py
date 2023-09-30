import sqlite3

conn = sqlite3.connect('database.db')
print("Connected to database successfully")

conn.execute(
    """
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            reservation_datetime DATETIME,
            reservation_first_name TEXT, 
            reservation_last_name TEXT, 
            phone_number TEXT, 
            reservation_token TEXT, 
            number_of_guests INTEGER
        )
    """
)
print("Created table successfully!")

conn.close()