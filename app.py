from flask import Flask, render_template, request, redirect, url_for, flash
from database.db import get_db_connection

app = Flask(__name__) #This creates a Flask application instance.

app.secret_key = "employee_management_secret"

@app.route('/')
def home():
    return "Welcome to Employee Management System"

@app.route('/test-db')
def testdb():
    try:
        connection = get_db_connection()
        if connection.is_connected():
            connection.close()
            return "MySQL Database Connected Successfully!"

    except Exception as e:
        return f"Database Connection Failed: {str(e)}"

# Step 1 - Employee Registration

@app.route('/add-employee', methods = ['GET', 'POST'])
def add_employee():
    if request.method == "POST":
        employee_code = request.form.get('employee_code', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        designation = request.form.get('designation', '').strip()
        salary = request.form.get('salary') or None
        joining_date = request.form.get('joining_date') or None
        status = request.form.get('status', 'active')

        if not employee_code or not first_name or not email:
            flash("Employee Code, First Name and Email are required.", "danger")
            return redirect(url_for('add_employee'))

        if status not in ('active', 'inactive'):
            flash("Invalid employee status", "danger")
            return redirect(url_for('add_employee'))

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            query = """
            INSERT INTO employees(
            employee_code,
            first_name,
            last_name,
            email,
            phone,
            department,
            designation,
            salary,
            joining_date,
            status
            ) values(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """
            values = (
                employee_code,
                first_name,
                last_name or None,
                email,
                phone or None,
                department or None,
                designation or None,
                salary,
                joining_date,
                status

            )

            cursor.execute(query,values)
            connection.commit()
            flash("Employee registered successfully!", "success")
            return redirect(url_for("add_employee"))

        except Exception as e:               #This block handles errors that occur inside the try block
            if connection:
                connection.rollback         #Cancel uncommitted database changes 

            flash(f"Error: {str(e)}", "danger")

        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():  #is_connected is default method by mysql checks connection statsu
                connection.close()

    return render_template("employee_add.html")

# Step 2 - Employee List

@app.route('/employee-list')
def employee_list():
    connection = None
    cursor = None

    try:
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM employees"
        cursor.execute(query)
        employees = cursor.fetchall()
        return render_template("employee_list.html", employees=employees)
    
    except Exception as e:
         import traceback
         traceback.print_exc()
         return f"Database Error: {str(e)}", 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# Step 3 - Employee Info
@app.route('/employee-info/<int:id>')
def employee_details(id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM employees where ID = %s"
        cursor.execute(query, (id,))
        employee = cursor.fetchone()

        if employee is None:
            return "No employee found", 404
        
        return render_template('employee_info.html', employee = employee)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Database Error: {str(e)}", 500
        

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route('/employee-edit/<int:id>')
def edit_employee(id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM employees where ID = %s"
        cursor.execute(query, (id,))
        employee = cursor.fetchone()
        if employee is None:
                    return "No employee found", 404
        return render_template('employee_add.html', employee = employee)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Database Errror: {str(e)}", 500


@app.route('/employee-update/<int:id>', methods=['POST'])
def update_employee(id):
       if request.method == "POST":
            employee_code = request.form.get('employee_code', '').strip()
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            department = request.form.get('department', '').strip()
            designation = request.form.get('designation', '').strip()
            salary = request.form.get('salary') or None
            joining_date = request.form.get('joining_date') or None
            status = request.form.get('status', 'active')

            connection = None
            cursor = None
            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                query = """
                UPDATE employees SET
                employee_code  = %s,
                first_name = %s,
                last_name = %s,
                email = %s,
                phone = %s,
                salary = %s,
                department = %s,
                designation = %s,
                joining_date = %s,
                status = %s
                WHERE id = %s
                """
                values = (
                    employee_code,
                    first_name,
                    last_name,
                    email,
                    phone,
                    salary,
                    department,
                    designation,
                    joining_date,
                    status,
                    id

                )
                cursor.execute(query, values)
                connection.commit()
                flash("Employee details updated successfully!", "success")
                return redirect(url_for('employee_list'))
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                return f"Database Errror: {str(e)}", 500
                
@app.route('/employee-delete/<int:id>', methods=['POST'])
def delete_employee(id):

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        query = "DELETE FROM employees WHERE id = %s"

        cursor.execute(query, (id,))
        connection.commit()

        if cursor.rowcount > 0:
            flash("Employee deleted successfully!", "success")
        else:
            flash("Employee not found!", "warning")

        return redirect(url_for('employee_list'))

    except Exception as e:

        if connection and connection.is_connected():
            connection.rollback()

        print("Database Error:", str(e))

        flash("Unable to delete employee.", "danger")

        return redirect(url_for('employee_list'))

    finally:

        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()
            
@app.route('/about')
def about():
    return "About Employee Management System"

@app.route('/departments')
def departments():
    return "Departments List"

@app.route('/contact')
def contact():
    return "Contact Us"



if __name__ == '__main__':
    app.run(debug=True)