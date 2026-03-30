from werkzeug.security import generate_password_hash, check_password_hash
from database import db
from datetime import datetime, UTC


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, default=True)
    assignments = db.relationship(
        "JobAssignment",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    contact_info = db.Column(db.String(200))
    job_type = db.Column(db.String(50))
    job_category = db.Column(db.String(100))
    scope_of_work = db.Column(db.Text)
    install_date = db.Column(db.Date)
    status = db.Column(db.String(50), default="scheduled")
    notes = db.relationship("JobNote", backref="job", lazy=True)
    assignments = db.relationship(
        "JobAssignment",
        backref="job",
        lazy=True,
        cascade="all, delete-orphan"
    )
    photos = db.relationship(
        "JobPhoto",
        backref="job",
        lazy=True,
        cascade="all, delete-orphan"
    )

    documents = db.relationship(
        "JobDocument",
        backref="job",
        lazy=True,
        cascade="all, delete-orphan"
    )

    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )


class JobAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    role = db.Column(db.String(50))


class JobNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    note_type = db.Column(db.String(50))
    content = db.Column(db.Text, nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    author = db.relationship("User")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class JobPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    photo_type = db.Column(db.String(50))
    file_path = db.Column(db.String(300), nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    
    uploader = db.relationship("User")


class JobFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    file_name = db.Column(db.String(200), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))


class JobDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    file_path = db.Column(db.String(255), nullable=False)

    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    # Relationship to User (who uploaded it)
    uploader = db.relationship("User")