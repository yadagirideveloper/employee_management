import mysql.connector

def get_db_connection():
    connection = mysql.connector.connect(
        host = "localhost",
        user = "root",
        password = "",
        database = "employee_management",
        port = "3306"
    )
    return connection