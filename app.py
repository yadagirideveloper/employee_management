from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from database.db import get_db_connection
import math
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from werkzeug.utils import secure_filename
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import jsonify

load_dotenv()

MAIL_SERVER = os.getenv('MAIL_SERVER')
MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')

app = Flask(__name__) #This creates a Flask application instance.

UPLOAD_FOLDER = os.path.join('static', 'uploads')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = os.getenv('SECRET_KEY')


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if 'user_id' not in session:
            flash("Please login to access this page!", "warning")
            return redirect(url_for('login'))

        return function(*args, **kwargs)

    return wrapper

def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
         
         if 'user_id' not in session:
            flash("Please login first!", "warning")
            return redirect(url_for('login'))

         if session.get('role') != 'admin':
            flash("Access denied! Admin permission required.", "danger")
            return redirect(url_for('employee_list'))

         return function(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route('/')
def home():
    return redirect(url_for('login'))

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

            token = generate_verification_token(email)

            verification_link = url_for(
                'verify_email',
                token=token,
                _external=True
            )

            subject = "Verify Your Email Addre"

            body = f"""
            Hello {name},

            Thank you for registering with Employee Management System.

            Please click the following link to verify your email address:

            {verification_link}

            This link expires in 1 hour.

            If you did not create this account, please ignore this email.
            """

            result = send_email(email, subject, body)

            if result:
                flash(
                    "Registration successful! Please check your email to verify your account.",
                    "success"
                )
            else:
                flash(
                    "Registration completed, but verification email could not be sent. Please contact support.",
                    "warning"
                )

            flash("Registration completed successfully, Please login!", "success")

            return redirect(url_for('login'))
        
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

                      if not user['is_verified']:
                          flash( "Please verify your email address before logging in.", "warning")
                          return redirect(url_for('login'))
                      
                      session['user_id'] = user['id']
                      session['name'] = user['name']
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

#logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have logged out successfully")
    return redirect(url_for('login'))


    

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
@admin_required
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
        profile_image = request.files.get('profile_image')
        image_filename = None

        if not employee_code or not first_name or not email:
            flash("Employee Code, First Name and Email are required.", "danger")
            return redirect(url_for('add_employee'))

        if status not in ('active', 'inactive'):
            flash("Invalid employee status", "danger")
            return redirect(url_for('add_employee'))

        if profile_image and profile_image.filename:

            if allowed_file(profile_image.filename):

                filename = secure_filename(profile_image.filename)
                image_filename = filename

                upload_path = os.path.join(
                    app.config['UPLOAD_FOLDER'],
                    image_filename
                )

                profile_image.save(upload_path)

            else:
                flash("Only JPG, JPEG and PNG images are allowed!", "danger")
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
            status,
            profile_image
            ) values(
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                status,
                image_filename

            )

            cursor.execute(query,values)
            connection.commit()
            flash("Employee registered successfully!", "success")
            return redirect(url_for("add_employee"))

        except Exception as e:               #This block handles errors that occur inside the try block
            if connection:
                connection.rollback()         #Cancel uncommitted database changes 

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
@admin_required
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
@admin_required
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
            profile_image = request.files.get('profile_image')

            connection = None
            cursor = None
            try:
                connection = get_db_connection()
                cursor = connection.cursor(dictionary=True)

                cursor.execute("SELECT * FROM employees WHERE id = %s",
                (id,))

                employee = cursor.fetchone()
                if not employee:
                    flash("Employee not found!", "danger")
                    return redirect(url_for('employee_list'))

                image_filename = employee['profile_image']

                if profile_image and profile_image.filename:
                    if allowed_file(profile_image.filename):
                        filename = secure_filename(profile_image.filename)

                        image_filename = filename

                        upload_path = os.path.join(
                            app.config['UPLOAD_FOLDER'],
                            image_filename
                        )

                        profile_image.save(upload_path)
                    else:
                            flash("Only JPG, JPEG and PNG images are allowed!", "danger")
                            return redirect(url_for('edit_employee', id=id))
                
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
                status = %s,
                profile_image = %s
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
                    image_filename,
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
@admin_required
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

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():

    if request.method == "POST":

        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_new_password = request.form.get('confirm_new_password', '')

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # 1. Get logged-in user details
            query = "SELECT * FROM users WHERE id = %s"
            values = (session['user_id'],)

            cursor.execute(query, values)
            user = cursor.fetchone()

            if not user:
                flash("User not found!", "danger")
                return redirect(url_for('login'))

            # 2. Verify current password
            if not check_password_hash(user['password'], current_password):
                flash("Current password is incorrect!", "danger")
                return redirect(url_for('change_password'))

            # 3. Validate new password
            if len(new_password) < 8:
                flash("New password must contain at least 8 characters!", "danger")
                return redirect(url_for('change_password'))

            # 4. Check password confirmation
            if new_password != confirm_new_password:
                flash("New password and confirmation do not match!", "danger")
                return redirect(url_for('change_password'))

            # 5. Hash new password
            hashed_password = generate_password_hash(new_password)

            # 6. Update password
            query = """
                UPDATE users
                SET password = %s
                WHERE id = %s
            """

            values = (hashed_password, session['user_id'])

            cursor.execute(query, values)
            connection.commit()

            flash("Password updated successfully!", "success")
            return redirect(url_for('dashboard'))

        except Exception as e:

            if connection:
                connection.rollback()

            print("Database Error:", str(e))
            flash("Unable to update password. Please try again.", "danger")

        finally:

            if cursor:
                cursor.close()

            if connection and connection.is_connected():
                connection.close()

    return render_template('change_password.html')

def send_email(to_email, subject, body):

    msg = EmailMessage()

    msg['Subject'] = subject
    msg['From'] = MAIL_DEFAULT_SENDER
    msg['To'] = to_email

    msg.set_content(body)

    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:

            server.starttls()

            server.login(MAIL_USERNAME, MAIL_PASSWORD)

            server.send_message(msg)

        return True

    except Exception as e:

        print("Email sending failed:", e)

        return False

@app.route('/test-email')
def test_email():

    result = send_email(
        'yourgmail@gmail.com',
        'Flask SMTP Test',
        'Congratulations! Gmail SMTP is working with Flask.'
    )

    if result:
        return "Email sent successfully!"

    return "Email sending failed!"

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():

    if request.method == 'POST':

        email = request.form.get('email', '').strip()

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,)
            )

            user = cursor.fetchone()

            if user:

                token = generate_reset_token(email)

                reset_link = url_for(
                    'reset_password',
                    token=token,
                    _external=True
                )

                subject = "Password Reset Request"

                body = f"""
Hello,

We received a request to reset your password.

Click the link below to reset your password:

{reset_link}

This link expires in 10 minutes.

If you did not request this, please ignore this email.
"""

                result = send_email(email, subject, body)

                if result:
                    flash("Password reset link sent to your email!", "success")
                else:
                    flash("Unable to send reset email. Please try again.", "danger")

            else:
                flash("If that email is registered, a reset link will be sent.", "info")

        except Exception as e:
            print("Forgot password error:", e)
            flash("Something went wrong. Please try again.", "danger")

        finally:
            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):

    email = verify_reset_token(token)

    if not email:
        return "Password reset link is invalid or expired."

    if request.method == 'POST':

        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or len(new_password) < 8:
            flash("Password must contain at least 8 characters.", "danger")

        elif new_password != confirm_password:
            flash("Passwords do not match!", "danger")

        else:

            hashed_password = generate_password_hash(new_password)

            connection = get_db_connection()
            cursor = connection.cursor()

            try:
                cursor.execute(
                    "UPDATE users SET password = %s WHERE email = %s",
                    (hashed_password, email)
                )

                connection.commit()

                flash("Password reset successfully. Please login.", "success")

                return redirect(url_for('login'))

            except Exception as e:
                connection.rollback()
                print("Password update error:", e)
                flash("Unable to update password.", "danger")

            finally:
                cursor.close()
                connection.close()

    return render_template('reset_password.html')

def generate_reset_token(email):

    serializer = URLSafeTimedSerializer(app.secret_key)

    token = serializer.dumps(email, salt='password-reset-salt')

    return token

def verify_reset_token(token, expiration=600):

    serializer = URLSafeTimedSerializer(app.secret_key)

    try:
        email = serializer.loads(
            token,
            salt='password-reset-salt',
            max_age=expiration
        )

        return email

    except (SignatureExpired, BadSignature):
        return None

def generate_verification_token(email):

    serializer = URLSafeTimedSerializer(app.secret_key)

    token = serializer.dumps(
        email,
        salt='email-verification-salt'
    )

    return token

@app.route('/verify-email/<token>')
def verify_email(token):

    email = verify_email_token(token)

    if not email:
        return "Verification link is invalid or expired."

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, is_verified FROM users WHERE email = %s",
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            flash("User account not found!", "danger")
            return redirect(url_for('login'))

        if user['is_verified']:
            flash("Your email is already verified!", "info")
            return redirect(url_for('login'))

        cursor.execute(
            "UPDATE users SET is_verified = 1 WHERE id = %s",
            (user['id'],)
        )

        connection.commit()

        flash(
            "Email verified successfully! You can now log in.",
            "success"
        )

        return redirect(url_for('login'))

    except Exception as e:

        if connection:
            connection.rollback()

        print("Email verification error:", e)

        flash("Email verification failed. Please try again.", "danger")

        return redirect(url_for('login'))

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


def verify_email_token(token, expiration=3600):

    serializer = URLSafeTimedSerializer(app.secret_key)

    try:

        email = serializer.loads(
            token,
            salt='email-verification-salt',
            max_age=expiration
        )

        return email

    except (SignatureExpired, BadSignature):

        return None



@app.route('/users')
@admin_required
def user_list():

    search = request.args.get('search', '').strip()
    role = request.args.get('role', '').strip()

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
        SELECT id, name, email, role, is_verified, status, created_at
        FROM users
        WHERE 1=1
    """

    values = []
    if search:
        query += """
            AND (name LIKE %s OR email LIKE %s)
        """
        search_value = f"%{search}%"
        values.extend([search_value, search_value])
    if role:
        query += " AND role = %s"
        values.append(role)

    query += " ORDER BY id DESC"

    cursor.execute(query, tuple(values))

    users = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template('user_list.html', users=users)

# Edit User
@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
def edit_user(id):

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT id, name, email, role FROM users WHERE id = %s",
        (id,)
    )

    user = cursor.fetchone()

    if not user:
        cursor.close()
        connection.close()
        flash("User not found!", "danger")
        return redirect(url_for('user_list'))

    if request.method == 'POST':

        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', '').strip()

        if not name or not email or role not in ['admin', 'user']:
             flash("Please enter valid user details.", "danger")
             return redirect(url_for('edit_user', id=id))
        try:
            cursor.execute(
                """
                UPDATE users
                SET name = %s, email = %s, role = %s
                WHERE id = %s
                """,
                (name, email, role, id)
            )
            connection.commit()
            flash("User updated successfully!", "success")
            return redirect(url_for('user_list'))
        except Exception as e:
            connection.rollback()
            print("Edit user error:", e)
            flash("Unable to update user. Email may already exist.", "danger")
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('edit_user', id=id))
    cursor.close()
    connection.close()

    return render_template('edit_user.html', user=user)
#User Update
@app.route('/user/update/<int:id>', methods = ['GET', 'POST'])
def update_user(id):
    connection = get_db_connection()
    cursor = connection.cursor()
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip()
        role = request.form.get('role')

        if not name or not email:
            flash("Name and email are required!", "danger")
            return redirect(url_for('edit_user', id=id))

        query = """UPDATE users SET name= %s, email = %s, role = %s where id = %s
        """
        values = (name, email, role, id)
        try:
            cursor.execute(query, values)
            connection.commit()
            flash("user updated sucessfully", 'sucess')
            return redirect(url_for('users_list'))
        except Exception as e:
            connection.rollback()
            print("Error user update failed :", e)
            flash("unable to update user details", 'danger')
        finally:
            cursor.close()
            connection.close()
        return redirect(url_for('edit_user', id=id))
    cursor.close()
    connection.close()
    return redirect(url_for('edit_user', id=id))

# user activate and de activate

@app.route('/users/change-status/<int:id>', methods=['POST'])
@admin_required
def change_user_status(id):

    connection = None
    cursor = None

    try:
        status = request.form.get('status', '').strip()

        if status not in ['Active', 'Inactive']:
            flash('Invalid user status.', 'danger')
            return redirect(url_for('user_list'))

        # Prevent admin from deactivating their own account
        if id == session.get('user_id') and status == 'Inactive':
            flash('You cannot deactivate your own account.', 'danger')
            return redirect(url_for('user_list'))

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            UPDATE users
            SET status = %s
            WHERE id = %s
        """

        cursor.execute(query, (status, id))

        if cursor.rowcount == 0:
            flash('User not found or status is unchanged.', 'warning')
        else:
            connection.commit()
            flash(f'User {status.lower()} successfully.', 'success')

    except Exception as e:
        if connection:
            connection.rollback()

        print("Change user status error:", e)
        flash('Unable to update user status.', 'danger')

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for('user_list'))

        
@app.route('/users/delete/<int:id>', methods=['POST'])
@admin_required
def delete_user(id):

    connection = None
    cursor = None

    try:
        # Prevent deleting your own account
        if id == session.get('user_id'):
            flash("You cannot delete your own account.", "danger")
            return redirect(url_for("user_list"))

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check whether user exists
        cursor.execute("SELECT id, role FROM users WHERE id = %s", (id,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.", "warning")
            return redirect(url_for("user_list"))

        # Prevent deleting the last active admin
        if user[1] == 'admin':
            cursor.execute("""
                SELECT COUNT(*) FROM users
                WHERE role = 'admin' AND status = 'Active'
            """)
            admin_count = cursor.fetchone()[0]

            if admin_count <= 1:
                flash("You cannot delete the last admin account.", "danger")
                return redirect(url_for("user_list"))

        query = "DELETE FROM users WHERE id = %s"
        cursor.execute(query, (id,))

        connection.commit()

        flash("User deleted successfully.", "success")

    except Exception as e:
        if connection:
            connection.rollback()

        print("Delete user error:", e)
        flash("Failed to delete user.", "danger")

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for("user_list"))

#API FLASK PYTHON

@app.route('/api/employees', methods=['GET'])
def get_employees():

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT id, first_name, email, department
            FROM employees
            ORDER BY id DESC
        """

        cursor.execute(query)

        employees = cursor.fetchall()

        return jsonify({
            "status": "success",
            "employees": employees
        }), 200

    except Exception as e:

        print("API Error:", e)

        return jsonify({
            "status": "error",
            "message": "Unable to fetch employees"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()
            
@app.route('/api/employees/<int:id>', methods=['GET'])
def get_employee(id):
     connection = None
     cursor = None
     
     try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)
    
            query = """
                SELECT id, first_name, email, department
                FROM employees where id = %s
            """
            values = (id,)
    
            cursor.execute(query, values)
    
            employees = cursor.fetchone()
        

            return jsonify({
                        "status": "success",
                        "employees": employees
                    }), 200
            
     except Exception as e:
            
                    print("API Error:", e)
            
                    return jsonify({
                        "status": "error",
                        "message": "Unable to fetch employees"
                    }), 500
            
     finally:
                    if cursor:
                        cursor.close()
            
                    if connection:
                        connection.close()



@app.route('/api/employees', methods=['POST'])
def create_employee():

    connection = None
    cursor = None

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "status": "error",
                "message": "JSON data is required"
            }), 400

        first_name = data.get('first_name', '').strip()
        email = data.get('email', '').strip()
        department = data.get('department', '').strip()

        if not first_name or not email or not department:
            return jsonify({
                "status": "error",
                "message": "All fields are required"
            }), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO employees (first_name, email, department)
            VALUES (%s, %s, %s)
        """

        values = (first_name, email, department)

        cursor.execute(query, values)
        connection.commit()

        employee_id = cursor.lastrowid

        return jsonify({
            "status": "success",
            "message": "Employee created successfully",
            "employee_id": employee_id
        }), 201

    except Exception as e:

        if connection:
            connection.rollback()

        print("API Error:", e)

        return jsonify({
            "status": "error",
            "message": "Unable to create employee"
        }), 500

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

@app.route('/api/employeupdate/<int:id>', methods=['PUT'])
def update_employeeapi(id):
    return jsonify({
        "status": "success",
        "message": "PUT API is working"
    }), 200


if __name__ == '__main__':
    app.run(debug=True)



