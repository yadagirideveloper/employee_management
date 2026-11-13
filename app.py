from flask import Flask, render_template, request, redirect, url_for, flash, session
from database.db import get_db_connection
import math
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__) #This creates a Flask application instance.

app.secret_key = "employee_management_secret"

@app.route('/')
def home():
    return "Welcome to Employee Management System"

@app.route('/dashboard')
def dashboard():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = "SELECT count(*) as total FROM employees"
        cursor.execute(query)
        total = cursor.fetchone()['total']

        query = """
        SELECT count(*) as active from employees where status = 'Active'
        """
        cursor.execute(query)
        active = cursor.fetchone()['active']

        query = """
        SELECT count(*) as inactive from employees where status = 'Inactive'
        """
        cursor.execute(query)
        inactive = cursor.fetchone()['inactive']

        query = """
        SELECT count(DISTINCT department) as departments from employees where department is not null
        and department != ''
        """
        cursor.execute(query)
        departments = cursor.fetchone()['departments']

        return render_template("dashboard.html", total_employees = total, active_employees = active,
                               inactive_employees = inactive, total_departments = departments)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Database Error: {str(e)}", 500
    finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

@app.route('/registration', methods = ['GET', 'POST'])
def register():
    connection = None
    cursor = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not name or not email or not password:
            flash("All fields are required!", "danger")
            return redirect(url_for('registration'))
        
        if len(password) < 8:
            flash("Password must be 8 characters", "danger")
            return redirect(url_for('registration'))

        try:
            hashed_password = generate_password_hash(password)
            connection = get_db_connection()
            cursor = connection.cursor()
            query = """
            INSERT INTO users(
            name,
            email,
            password
            )values(%s, %s, %s)
            """
            values = (name, email, hashed_password)

            cursor.execute(query, values)
            connection.commit()

            flash("Registration completed successfully!", "success")

            return redirect(url_for('register'))
        
        except Exception as e:

            if connection and connection.is_connected():
                connection.rollback()

            import traceback

            traceback.print_exc()

            flash("Registration failed. Email may already exist.", "danger")

            return redirect(url_for('register'))
        
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    return render_template('register.html')

        
@app.route('/login', methods = ['GET', 'POST'])
def login():
    connection = None
    cursor = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        if not email or not password:
            flash("email and password are manafdatory", "danger")
            return redirect(url_for('login'))
        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            query = """
            SELECT * FROM users where email = %s
            """
            cursor.execute(query, (email,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['role'] = user['role']

                flash("Login successful!", "success")

                return redirect(url_for('dashboard'))
            else:
                flash("Invalid password", "danger")
                return redirect(url_for('login'))
            
        except Exception as e:
            import traceback
            traceback.print_exc()

            flash("Something went wrong. Please try again.", "danger")

            return redirect(url_for('login'))
        finally:
            
            if cursor:
                cursor.close()

            if connection and connection.is_connected():
                connection.close()

    return render_template('login.html')


    


    

# @app.route('/test-db')
# def testdb():
#     try:
#         connection = get_db_connection()
#         if connection.is_connected():
#             connection.close()
#             return "MySQL Database Connected Successfully!"

#     except Exception as e:
#         return f"Database Connection Failed: {str(e)}"

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
        search = request.args.get('search', '').strip()
        department = request.args.get('department', '').strip()
          # Get pagination values
        page = request.args.get('page', 1, type=int)
        per_page = 5
        if page < 1:
            page = 1
        offset = (page - 1) * per_page

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True,
            buffered=True
        )

        query = """
            SELECT * FROM employees
            WHERE 1=1
        """
        count_query = """
            SELECT COUNT(*) AS total
            FROM employees
            WHERE 1=1
        """

        values = []

        # Search condition
        if search:
            search_condition = """
                AND (
                    employee_code LIKE %s
                    OR first_name LIKE %s
                    OR last_name LIKE %s
                    OR email LIKE %s
                    OR department LIKE %s
                )
            """

            query += search_condition
            count_query += search_condition

            search_value = f"%{search}%"

            values.extend([
                search_value,
                search_value,
                search_value,
                search_value,
                search_value
            ])

        # Department filter
        if department:
            query += " AND department = %s"
            count_query += " AND department = %s"

            values.append(department)

        
        cursor.execute(count_query, tuple(values))
        #total_employees = cursor.fetchone()['total']
        result = cursor.fetchone()

        if result:
            total_employees = result['total']
        else:
            total_employees = 0

         # Calculate total pages
        total_pages = math.ceil(total_employees / per_page)

         # Get employees for current page
        query += " ORDER BY id DESC LIMIT %s OFFSET %s"

        pagination_values = values + [per_page, offset]

        cursor.execute(query, tuple(pagination_values))

        employees = cursor.fetchall()


        return render_template(
            "employee_list.html",
            employees=employees,
            search=search,
            department=department,
            page=page,
            total_pages=total_pages
        )
    
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