from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory
from database import db
from models import Job, User, JobAssignment, JobPhoto, JobDocument

from datetime import datetime
from PIL import Image

from werkzeug.utils import secure_filename
import os
import uuid

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS



def create_app():
    app = Flask(__name__)

    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB

    app.config["SECRET_KEY"] = "super-secret-key"

    # Absolute path to database file
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, "instance", "app.db")

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["UPLOAD_FOLDER"] = os.path.join(os.getcwd(), "uploads")

    app.config["PHOTO_UPLOAD_FOLDER"] = os.path.join(app.config["UPLOAD_FOLDER"], "photos")
    app.config["DOCUMENT_UPLOAD_FOLDER"] = os.path.join(app.config["UPLOAD_FOLDER"], "documents")

    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

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

    #--------------------------------
    # User Management
    #--------------------------------
    @app.route("/users")
    def manage_users():

    # Only admins/office allowed
        if session.get("user_role") != "admin":
            abort(403)

        users = User.query.all()

        return render_template("users.html", users=users)
    
    @app.route("/users/create", methods=["POST"])
    def create_user():

        if session.get("user_role") != "admin":
            abort(403)

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        from werkzeug.security import generate_password_hash

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            active=True
        )

        db.session.add(user)
        db.session.commit()

        flash("User created successfully.")

        return redirect(url_for("manage_users"))
    
    #----------------------------------------------------
    #User edit 
    #----------------------------------------------------
    @app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
    def edit_user(user_id):

        if session.get("user_role") != "admin":
            abort(403)

        user = User.query.get_or_404(user_id)

        if request.method == "POST":

            user.name = request.form.get("name")
            user.email = request.form.get("email")
            user.role = request.form.get("role")

            db.session.commit()

            flash("User updated successfully.")

            return redirect(url_for("manage_users"))

        return render_template("edit_user.html", user=user)
    
    #-----------------------------------------------------
    # password reset
    #-----------------------------------------------------
    @app.route("/users/<int:user_id>/reset_password", methods=["POST"])
    def reset_password(user_id):

        # Only admin/office allowed
        if session.get("user_role") != "admin":
            abort(403)

        user = User.query.get_or_404(user_id)

        new_password = request.form.get("new_password")

        if not new_password:
            flash("Password cannot be empty.")
            return redirect(url_for("manage_users"))

        from werkzeug.security import generate_password_hash

        user.password_hash = generate_password_hash(new_password)

        db.session.commit()

        flash(f"Password reset for {user.name}.")

        return redirect(url_for("manage_users"))
    
    #---------------------------------------------
    # user activate/deactivate
    #---------------------------------------------
    @app.route("/users/<int:user_id>/toggle_active", methods=["POST"])
    def toggle_user_active(user_id):

        # Only admin/office allowed
        if session.get("user_role") != "admin":
            abort(403)

        user = User.query.get_or_404(user_id)

        # Prevent self-deactivation (important)
        if user.id == session.get("user_id"):
            flash("You cannot deactivate your own account.")
            return redirect(url_for("manage_users"))

        user.active = not user.active

        db.session.commit()

        flash("User status updated.")

        return redirect(url_for("manage_users"))

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

        user_role = session.get("user_role")

        active_statuses = [
            "to_be_scheduled",
            "scheduled",
            "on_site",
            "in_progress",
            "needs_return_visit"
        ]

        if user_role == "admin":
            jobs = Job.query.filter(
                Job.status.in_(active_statuses)
            ).order_by(Job.created_at.desc()).all()

        else:
            user_id = session.get("user_id")

            jobs = (
                db.session.query(Job)
                .join(JobAssignment)
                .filter(
                    JobAssignment.user_id == user_id,
                    Job.status.in_(active_statuses)
                )
                .order_by(Job.created_at.desc())
                .all()
            )

        return render_template("jobs.html", jobs=jobs)
    
    #----------------------------------------------------------
    # to measure
    #----------------------------------------------------------
    @app.route("/jobs/to_measure")
    def to_measure_jobs():

        jobs = Job.query.filter_by(
            status="needs_measurement"
        ).order_by(Job.created_at.desc()).all()

        return render_template("to_measure_jobs.html", jobs=jobs)
    
    #-----------------------------------------------------------------
    # Mark measued button
    #------------------------------------------------------------------
    @app.route("/jobs/<int:job_id>/mark_measured", methods=["POST"])
    def mark_measured(job_id):

        job = Job.query.get_or_404(job_id)

        user_role = session.get("user_role") or session.get("role")

        if not user_role or user_role not in ["admin", "installer"]:
            abort(403)

        if job.status != "needs_measurement":
            abort(400)

        job.status = "to_be_scheduled"
        db.session.commit()

        return redirect(url_for("to_measure_jobs"))

    #------------------------------------------------------------
    # completed jobs
    #------------------------------------------------------------
    @app.route("/jobs/completed")
    def completed_jobs():

        if session.get("user_role") != "admin":
            abort(403)

        jobs = Job.query.filter_by(
            status="completed"
        ).order_by(Job.created_at.desc()).all()

        return render_template("completed_jobs.html", jobs=jobs)

    # --------------------
    # Job Detail
    # --------------------
    @app.route("/jobs/<int:job_id>")
    def job_detail(job_id):

        job = Job.query.get_or_404(job_id)

        if session.get("user_role") == "installer":
            user_id = session.get("user_id")

            assignment = JobAssignment.query.filter_by(
                job_id=job.id,
                user_id=user_id
            ).first()

            if not assignment and job.status != "needs_measurement":
                abort(403)

        user = User.query.get(session["user_id"])

        
        installers = User.query.filter_by(role="installer", active=True).all()

        return render_template(
            "job_detail.html",
            job=job,
            user=user,
            installers=installers
        )
    
    #-------------------------------------------------------
    #installer assign route
    #------------------------------------------------------
    @app.route("/jobs/<int:job_id>/assign", methods=["POST"])
    def assign_installer(job_id):

        if session.get("user_role") != "admin":
            abort(403)

        job = Job.query.get_or_404(job_id)

        user_id = request.form.get("user_id")

        # prevent duplicates
        existing = JobAssignment.query.filter_by(
            job_id=job.id,
            user_id=user_id
        ).first()

        if existing:
            flash("Installer already assigned.")
            return redirect(url_for("job_detail", job_id=job.id))

        assignment = JobAssignment(
            job_id=job.id,
            user_id=user_id
        )

        db.session.add(assignment)
        db.session.commit()

        flash("Installer assigned.")

        return redirect(url_for("job_detail", job_id=job.id))
    
    @app.route("/assignments/<int:assignment_id>/delete", methods=["POST"])
    def remove_assignment(assignment_id):

        if session.get("user_role") != "admin":
            abort(403)

        assignment = JobAssignment.query.get_or_404(assignment_id)

        job_id = assignment.job_id

        db.session.delete(assignment)
        db.session.commit()

        flash("Installer removed.")

        return redirect(url_for("job_detail", job_id=job_id))
    
    #--------------------------------------------------------
    # Dpcument upload route
    #--------------------------------------------------------
    @app.route("/jobs/<int:job_id>/upload_document", methods=["POST"])
    def upload_document(job_id):

        job = Job.query.get_or_404(job_id)

        if "document" not in request.files:
            flash("No file uploaded.")
            return redirect(url_for("job_detail", job_id=job.id))

        file = request.files["document"]

        if file.filename == "":
            flash("No file selected.")
            return redirect(url_for("job_detail", job_id=job.id))

        # Only allow PDFs
        if not file.filename.lower().endswith(".pdf"):
            flash("Only PDF files are allowed.")
            return redirect(url_for("job_detail", job_id=job.id))

        import uuid
        from werkzeug.utils import secure_filename

        original_filename = secure_filename(file.filename)
        extension = ".pdf"

        unique_filename = f"{uuid.uuid4().hex}{extension}"

        filepath = os.path.join(app.config["DOCUMENT_UPLOAD_FOLDER"], unique_filename)
        file.save(filepath)

        document = JobDocument(
            job_id=job.id,
            uploaded_by=session["user_id"],
            file_path=unique_filename
        )

        db.session.add(document)
        db.session.commit()

        flash("Document uploaded successfully.")

        return redirect(url_for("job_detail", job_id=job.id))
    
    #-----------------------------------------------
    # Document delete route
    #-----------------------------------------------
    @app.route("/documents/<int:doc_id>/delete", methods=["POST"])
    def delete_document(doc_id):

        doc = JobDocument.query.get_or_404(doc_id)

        user = User.query.get(session["user_id"])

        if user.role == "installer" and doc.uploaded_by != user.id:
            abort(403)

        filepath = os.path.join(app.config["DOCUMENT_UPLOAD_FOLDER"], doc.file_path)

        if os.path.exists(filepath):
            os.remove(filepath)

        job_id = doc.job_id

        db.session.delete(doc)
        db.session.commit()

        flash("Document deleted.")

        return redirect(url_for("job_detail", job_id=job_id))
    
    #--------------
    # Photo Upload Route
    #--------------
    @app.route("/jobs/<int:job_id>/upload_photo", methods=["POST"])
    def upload_photo(job_id):

        job = Job.query.get_or_404(job_id)

        if "photo" not in request.files:
            flash("No photo uploaded.")
            return redirect(url_for("job_detail", job_id=job.id))

        file = request.files["photo"]

        if file.filename == "":
            flash("No file selected.")
            return redirect(url_for("job_detail", job_id=job.id))

        if not allowed_file(file.filename):
            flash("Unsupported file type. Please upload JPG or PNG images.")
            return redirect(url_for("job_detail", job_id=job.id))

        # 🔥 ALWAYS SAVE AS JPG NOW
        unique_filename = f"{uuid.uuid4().hex}.jpg"

        os.makedirs(app.config["PHOTO_UPLOAD_FOLDER"], exist_ok=True)
        filepath = os.path.join(app.config["PHOTO_UPLOAD_FOLDER"], unique_filename)

        # 🔥 OPEN IMAGE WITH PIL
        image = Image.open(file)

        # Convert to RGB (fixes PNG, HEIC, etc.)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if too large
        max_width = 1280
        if image.width > max_width:
            ratio = max_width / float(image.width)
            new_height = int(image.height * ratio)
            image = image.resize((max_width, new_height))

        # 🔥 SAVE COMPRESSED
        image.save(filepath, "JPEG", quality=75, optimize=True)

        # Save to DB
        photo = JobPhoto(
            job_id=job.id,
            uploaded_by=session["user_id"],
            file_path=unique_filename
        )

        db.session.add(photo)
        db.session.commit()

        flash("Photo uploaded successfully.")

        return redirect(url_for("job_detail", job_id=job.id))

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
    
    #---------------------------------------------------------------------------------
    # photo upload exceeded size error message
    #---------------------------------------------------------------------------------
    @app.errorhandler(413)
    def too_large(e):
        flash("File too large. Maximum size is 10MB.")
        return redirect(request.referrer or url_for("list_jobs"))
    
    #---------------------------------------------
    # Delete photos route
    #---------------------------------------------
    @app.route("/photos/<int:photo_id>/delete", methods=["POST"])
    def delete_photo(photo_id):

        photo = JobPhoto.query.get_or_404(photo_id)

        # Get current user
        user = User.query.get(session["user_id"])

        # Permission check
        # Office/admin can delete anything
        # Installers can only delete their own photos
        if user.role == "installer" and photo.uploaded_by != user.id:
            abort(403)

        filepath = os.path.join(app.config["PHOTO_UPLOAD_FOLDER"], photo.file_path)

        # Delete file from disk
        if os.path.exists(filepath):
            os.remove(filepath)

        job_id = photo.job_id

        db.session.delete(photo)
        db.session.commit()

        flash("Photo deleted.")

        return redirect(url_for("job_detail", job_id=job_id))

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
        installers = User.query.filter_by(role="installer", active=True).all()

        if session.get("user_role") != "admin":
            abort(403)

        if request.method == "POST":

            install_date_str = request.form.get("install_date")
            installer_ids = request.form.getlist("installers")


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

            from models import JobAssignment
            for installer_id in installer_ids:
                assignment = JobAssignment(
                    job_id=job.id,
                    user_id=installer_id,
                    role="Installer"
                )

                db.session.add(assignment)

            db.session.commit()


            return redirect(url_for("list_jobs"))

        return render_template("create_job.html", installers=installers)
    
    #---------------------------------------------------------
    #Created Job Edit
    #---------------------------------------------------------
    @app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
    def edit_job(job_id):

    # Only admin/office
        if session.get("user_role") != "admin":
            abort(403)

        job = Job.query.get_or_404(job_id)

        if request.method == "POST":

            job.customer_name = request.form.get("customer_name")
            job.address = request.form.get("address")
            job.contact_info = request.form.get("contact_info")
            job.job_type = request.form.get("job_type")
            job.job_category = request.form.get("job_category")
            job.scope_of_work = request.form.get("scope_of_work")

            db.session.commit()

            flash("Job updated successfully.")

            return redirect(url_for("job_detail", job_id=job.id))

        return render_template("edit_job.html", job=job)
    
    #-------------------------------------------------------------------
    #job deletion
    #-------------------------------------------------------------------
    @app.route("/jobs/<int:job_id>/delete", methods=["POST"])
    def delete_job(job_id):

        if session.get("user_role") != "admin":
            abort(403)

        job = Job.query.get_or_404(job_id)

        db.session.delete(job)
        db.session.commit()

        flash("Job deleted successfully.")

        return redirect(url_for("list_jobs"))

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
    #@app.route("/create-admin")
    #def create_admin():

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

                # block inactive user
                if not user.active:
                    flash("Your account is inactive.")
                    return redirect(url_for("login"))

                session["user_id"] = user.id
                session["user_name"] = user.name
                session["user_role"] = user.role

                return redirect(url_for("home"))

            flash("Invalid email or password")
            return redirect(url_for("login"))

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
    app.run(host="0.0.0.0", port=5000, debug=True)