import re
from flask import Flask, render_template, request, redirect, session
import mysql.connector

app = Flask(__name__)
app.secret_key = "secret123"

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="placement_system"
)

cursor = db.cursor()

# ================= STUDENT DASHBOARD =================
@app.route('/')
def student_dashboard():
    if 'user' not in session:
        return redirect('/login')

    email = session['user']

    search = request.args.get('search', '')
    job_type = request.args.get('type', '')

    # Student details
    cursor.execute("SELECT * FROM Student WHERE Email=%s", (email,))
    student = cursor.fetchone()

    # BASE JOB QUERY + FILTER LOGIC
    query = """
    SELECT 
        Job.Job_ID,
        Job.Role,
        Job.Type,
        Job.Eligibility_Criteria,
        Job.Salary,
        Company.Company_Name,
        Company.Location
    FROM Job
    JOIN Company ON Job.Company_ID = Company.Company_ID
    WHERE 1=1
    """

    params = []

    if search:
        query += " AND (Job.Role LIKE %s OR Company.Company_Name LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    if job_type:
        query += " AND Job.Type = %s"
        params.append(job_type)

    cursor.execute(query, params)
    jobs = cursor.fetchall()

    # Applications
    cursor.execute("""
    SELECT 
        Application.Application_ID,
        Job.Role,
        Company.Company_Name,
        Application.Application_Status
    FROM Application
    JOIN Job ON Application.Job_ID = Job.Job_ID
    JOIN Company ON Job.Company_ID = Company.Company_ID
    JOIN Student ON Application.Student_ID = Student.Student_ID
    WHERE Student.Email = %s
    """, (email,))
    applications = cursor.fetchall()

    # Applied jobs
    cursor.execute("""
    SELECT Job.Job_ID
    FROM Application
    JOIN Student ON Application.Student_ID = Student.Student_ID
    JOIN Job ON Application.Job_ID = Job.Job_ID
    WHERE Student.Email = %s
    """, (email,))
    applied_jobs = [row[0] for row in cursor.fetchall()]

    return render_template(
        'student_dashboard.html',
        student=student,
        jobs=jobs,
        applications=applications,
        applied_jobs=applied_jobs
    )


# ================= ADMIN DASHBOARD =================
@app.route('/admin')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin_login')

    cursor.execute("SELECT * FROM Student")
    students = cursor.fetchall()

    cursor.execute("SELECT * FROM Company")
    companies = cursor.fetchall()

    cursor.execute("SELECT * FROM Job")
    jobs = cursor.fetchall()

    cursor.execute("""
    SELECT 
        Application.Application_ID,
        Student.Name,
        Job.Role,
        Company.Company_Name,
        Application.Application_Status
    FROM Application
    JOIN Student ON Application.Student_ID = Student.Student_ID
    JOIN Job ON Application.Job_ID = Job.Job_ID
    JOIN Company ON Job.Company_ID = Company.Company_ID
    """)
    applications = cursor.fetchall()

    # 📊 CHART DATA (IMPORTANT ADDITION)
    cursor.execute("""
    SELECT Application_Status, COUNT(*)
    FROM Application
    GROUP BY Application_Status
    """)
    status_data = cursor.fetchall()

    labels = [row[0] for row in status_data]
    values = [row[1] for row in status_data]

    return render_template(
        'admin_dashboard.html',
        students=students,
        companies=companies,
        jobs=jobs,
        applications=applications,
        labels=labels,
        values=values
    )

# ================= STUDENT LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    session.pop('admin', None)

    if request.method == 'POST':
        email = request.form['email']

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return render_template('login.html', error="Invalid Email Format")

        cursor.execute("SELECT * FROM Student WHERE Email = %s", (email,))
        user = cursor.fetchone()

        if user:
            session['user'] = email
            return redirect('/')
        else:
            return render_template('login.html', error="Email not found")

    return render_template('login.html')


# ================= ADMIN LOGIN =================
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    session.pop('user', None)

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if email == "admin@gmail.com" and password == "admin123":
            session['admin'] = True
            return redirect('/admin')

        return render_template('admin_login.html', error="Invalid Credentials")

    return render_template('admin_login.html')


# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ================= ADD STUDENT =================
@app.route('/add_student', methods=['POST'])
def add_student():
    if 'admin' not in session:
        return "Access Denied"

    name = request.form['name']
    email = request.form['email']
    cgpa = float(request.form['cgpa'])

    if cgpa < 0 or cgpa > 10:
        return redirect('/admin')

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return redirect('/admin')

    cursor.execute("""
    INSERT INTO Student (Name, Email, Department, CGPA, Skills, Resume)
    VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        name,
        email,
        request.form['dept'],
        cgpa,
        request.form['skills'],
        request.form['resume']
    ))

    db.commit()
    return redirect('/admin')


# ================= ADD COMPANY =================
@app.route('/add_company', methods=['POST'])
def add_company():
    if 'admin' not in session:
        return "Access Denied"

    cursor.execute("""
    INSERT INTO Company (Company_Name, Location, Industry_Type, Contact_Details)
    VALUES (%s,%s,%s,%s)
    """, (
        request.form['name'],
        request.form['location'],
        request.form['industry'],
        request.form['contact']
    ))

    db.commit()
    return redirect('/admin')


# ================= ADD JOB =================
@app.route('/add_job', methods=['POST'])
def add_job():
    if 'admin' not in session:
        return "Access Denied"

    cursor.execute("""
    INSERT INTO Job (Role, Type, Eligibility_Criteria, Salary, Company_ID)
    VALUES (%s,%s,%s,%s,%s)
    """, (
        request.form['role'],
        request.form['type'],
        request.form['criteria'],
        request.form['salary'],
        request.form['company_id']
    ))

    db.commit()
    return redirect('/admin')


# ================= APPLY JOB =================
@app.route('/apply/<int:job_id>')
def apply(job_id):
    if 'user' not in session:
        return redirect('/login')

    email = session['user']

    cursor.execute("SELECT Student_ID FROM Student WHERE Email=%s", (email,))
    student = cursor.fetchone()

    if not student:
        return "Student not found"

    student_id = student[0]

    # Prevent duplicate application
    cursor.execute("""
    SELECT * FROM Application 
    WHERE Student_ID=%s AND Job_ID=%s
    """, (student_id, job_id))

    if cursor.fetchone():
        return redirect('/')

    cursor.execute("""
    INSERT INTO Application (Student_ID, Job_ID, Application_Status)
    VALUES (%s,%s,%s)
    """, (student_id, job_id, "Applied"))

    db.commit()
    return redirect('/')


# ================= DELETE STUDENT =================
@app.route('/delete_student/<int:id>')
def delete_student(id):
    if 'admin' not in session:
        return "Access Denied"

    cursor.execute("DELETE FROM Application WHERE Student_ID=%s", (id,))
    cursor.execute("DELETE FROM Student WHERE Student_ID=%s", (id,))
    db.commit()

    return redirect('/admin')


# ================= EDIT STUDENT =================
@app.route('/edit_student/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if 'admin' not in session:
        return "Access Denied"

    if request.method == 'POST':
        cursor.execute("""
        UPDATE Student 
        SET Name=%s, Email=%s 
        WHERE Student_ID=%s
        """, (
            request.form['name'],
            request.form['email'],
            id
        ))
        db.commit()
        return redirect('/admin')

    cursor.execute("SELECT * FROM Student WHERE Student_ID=%s", (id,))
    student = cursor.fetchone()

    return render_template('edit_student.html', student=student)


# ================= EDIT COMPANY =================
@app.route('/edit_company/<int:id>', methods=['GET', 'POST'])
def edit_company(id):
    if 'admin' not in session:
        return "Access Denied"

    if request.method == 'POST':
        cursor.execute("""
        UPDATE Company 
        SET Company_Name=%s, Location=%s 
        WHERE Company_ID=%s
        """, (
            request.form['name'],
            request.form['location'],
            id
        ))
        db.commit()
        return redirect('/admin')

    cursor.execute("SELECT * FROM Company WHERE Company_ID=%s", (id,))
    company = cursor.fetchone()

    return render_template('edit_company.html', company=company)


# ================= EDIT JOB =================
@app.route('/edit_job/<int:id>', methods=['GET', 'POST'])
def edit_job(id):
    if 'admin' not in session:
        return "Access Denied"

    if request.method == 'POST':
        cursor.execute("""
        UPDATE Job 
        SET Role=%s, Salary=%s 
        WHERE Job_ID=%s
        """, (
            request.form['role'],
            request.form['salary'],
            id
        ))
        db.commit()
        return redirect('/admin')

    cursor.execute("SELECT * FROM Job WHERE Job_ID=%s", (id,))
    job = cursor.fetchone()

    return render_template('edit_job.html', job=job)


# ================= UPDATE STATUS =================
@app.route('/update_status/<int:id>', methods=['POST'])
def update_status(id):
    if 'admin' not in session:
        return "Access Denied"

    cursor.execute("""
    UPDATE Application 
    SET Application_Status=%s 
    WHERE Application_ID=%s
    """, (
        request.form['status'],
        id
    ))

    db.commit()
    return redirect('/admin')


# ================= RUN APP =================
if __name__ == '__main__':
    app.run(debug=True)