from flask import Flask, render_template, request, redirect, url_for, session
from database import db
from models import Job, User
from datetime import datetime
from flask import abort
import os


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = "super-secret-key"

    # Absolute path to database file
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, "instance", "app.db")

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    # --------------------
    # Global Login Guard
    # --------------------
    @app.before_request
    def require_login():
        allowed_routes = ["login", "create_admin", "static"]

        if request.endpoint not in allowed_routes:
            if "user_id" not in session:
                return redirect(url_for("login"))

    # --------------------
    # Home Page
    # --------------------
    @app.route("/")
    def home():
        return render_template("home.html")

    # --------------------
    # Job List
    # --------------------
    @app.route("/jobs")
    def list_jobs():
        jobs = Job.query.all()
        return render_template("jobs.html", jobs=jobs)

    # --------------------
    # Job Detail
    # --------------------
    @app.route("/jobs/<int:job_id>")
    def job_detail(job_id):
        job = Job.query.get_or_404(job_id)
        return render_template("job_detail.html", job=job)

    # --------------------
    # Add Job Note
    # --------------------
    @app.route("/jobs/<int:job_id>/notes", methods=["POST"])
    def add_job_note(job_id):

        job = Job.query.get_or_404(job_id)

        content = request.form.get("content")

        if content:
            from models import JobNote

            note = JobNote(
                job_id=job.id,
                user_id=session["user_id"],
                note_type="general",
                content=content
            )

            db.session.add(note)
            db.session.commit()

        return redirect(url_for("job_detail", job_id=job.id))

    # --------------------
    # Create Job
    # --------------------
    @app.route("/jobs/new", methods=["GET", "POST"])
    def create_job():

        if session.get("user_role") != "admin":
            abort(403)

        if request.method == "POST":

            install_date_str = request.form.get("install_date")

            if install_date_str:
                install_date_obj = datetime.strptime(
                    install_date_str, "%Y-%m-%d"
                ).date()
            else:
                install_date_obj = None

            job = Job(
                customer_name=request.form["customer_name"],
                address=request.form["address"],
                contact_info=request.form["contact_info"],
                job_type=request.form["job_type"],
                job_category=request.form["job_category"],
                scope_of_work=request.form["scope_of_work"],
                install_date=install_date_obj,
                status=request.form["status"]
            )

            db.session.add(job)
            db.session.commit()

            return redirect(url_for("list_jobs"))

        return render_template("create_job.html")

    # --------------------
    # Update Job Status
    # --------------------
    @app.route("/jobs/<int:job_id>/status", methods=["POST"])
    def update_job_status(job_id):

        job = Job.query.get_or_404(job_id)

        new_status = request.form.get("status")

        if new_status:
            job.status = new_status
            db.session.commit()

        return redirect(url_for("job_detail", job_id=job.id))

    # --------------------
    # Create Admin User (temporary)
    # --------------------
    @app.route("/create-admin")
    def create_admin():

        existing = User.query.filter_by(email="admin@glass.local").first()

        if existing:
            return "Admin already exists"

        admin = User(
            name="Admin",
            email="admin@glass.local",
            role="admin",
            active=True
        )

        admin.set_password("admin123")

        db.session.add(admin)
        db.session.commit()

        return "Admin user created"

    # --------------------
    # Login
    # --------------------
    @app.route("/login", methods=["GET", "POST"])
    def login():

        if request.method == "POST":

            email = request.form.get("email")
            password = request.form.get("password")

            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):

                session["user_id"] = user.id
                session["user_name"] = user.name
                session["user_role"] = user.role

                return redirect(url_for("home"))

            return "Invalid email or password"

        return render_template("login.html")

    # --------------------
    # Logout
    # --------------------
    @app.route("/logout")
    def logout():

        session.clear()

        return redirect(url_for("login"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)