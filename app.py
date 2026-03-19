from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String
from sqlalchemy import Column, Integer, String, Enum, Date, Time, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, backref
import os
from flask import request, jsonify, session, redirect, url_for
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import render_template
from googleapiclient.discovery import build
from flask_softdelete import SoftDeleteMixin
from flask_migrate import Migrate
from flask import render_template

app = Flask(__name__, static_folder='.', static_url_path='')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)
app.secret_key = os.environ["SECRET_KEY"]

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    db_url = "sqlite:///local.db"   # local dev
#render sometimes gives postgres://, sqlalchemy needs postgresql://
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
migrate = Migrate(app, db)

# creating a volunteer class
#class Volunteer(db.Model, SoftDeleteMixin):
class Volunteer(db.Model, SoftDeleteMixin):

    __tablename__ = "volunteers"

    id = Column(Integer, primary_key=True)

    first_name = Column(String(50))
    last_name = Column(String(50))

    email = Column(String(100), unique=True)

# for people signing up to volunteer that will be placed in inbox
class Applicant(db.Model, SoftDeleteMixin):
    __tablename__ = "applicants"

    id = Column(Integer, primary_key=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    email = Column(String(50))
    phone = Column(String(50))
    availability = Column(String(50))
    
# creating user account class
# only admins and captains should have be on this table
class UserAccount(db.Model, SoftDeleteMixin):
    __tablename__ = "user_account"

    user_id = Column(Integer, primary_key=True)
    volunteer_id = Column(Integer, ForeignKey("volunteers.id"), unique=True)
    password = Column(String(255), nullable=False)
    role = Column(
        Enum(
            "admin",
            "captain",
            "volunteer",
            "other",
            name="role_enum"
        ), nullable=False
    ) 
    volunteer = relationship("Volunteer", backref="account")

# creating a stations table
class Station(db.Model, SoftDeleteMixin):
    __tablename__ = "station"
    station_id = Column(Integer, primary_key=True)
    is_absent = Column(Boolean, default = False, nullable = False)
    station_name = Column(
        Enum(
            "Setup Team",
            "Teardown Team",
            "Line Servers",
            "Kitchen",
            "Drink Station",
            "Desserts",
            "Busboys/sanitation",
            "Dishwashers",
            "Reserve",
            "General Manager",
            "Greeters",
            "Baked Potato Bar",
            "Salad Bar",
            "Absent",
            "Other",
            name="station_enum"
        )
    )

# creating schedule table
class Schedule(db.Model, SoftDeleteMixin):
    __tablename__ = "schedule"
    schedule_id = Column(Integer, primary_key=True)
    date = Column(Date)
    time = Column(Time)

# creating assignment table
class Assignment(db.Model, SoftDeleteMixin):
    __tablename__ = "assignments"
    assignment_id = Column(Integer, primary_key=True)
    
    volunteer_id = Column(Integer, ForeignKey("volunteers.id"))
    station_id = Column(Integer, ForeignKey("station.station_id"))
    schedule_id = Column(Integer, ForeignKey("schedule.schedule_id"))
    
    created_by = Column(Integer, ForeignKey("user_account.user_id"))

   # original_station_id = Column(Integer, ForeignKey("station.station_id"))

    volunteer = relationship("Volunteer", backref = "assignments")
    station = relationship("Station", backref = "assignments")
    schedule = relationship("Schedule", backref = "assignments")

# creating a class that will store the availiablity hours for each person
class Availability(db.Model, SoftDeleteMixin):
    __tablename__ = "availability"

    availability_id = Column(Integer, primary_key=True)

    volunteer_id = Column(Integer, ForeignKey("volunteers.id"))

    hour = Column(String(50))       # Example: 8, 9, 10, 11

    volunteer = relationship("Volunteer", backref=backref("availability", cascade = "all, delete-orphan"))

if os.environ.get("RUN_DB_INIT") == "1":
    with app.app_context():
        db.create_all()
        
# Serve your existing HTML pages
@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(".", path)

@app.route("/api/google-login", methods=["POST"])
def google_login():
    GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
    token = request.json.get("credential")

    if not token:
        return jsonify({"error": "Missing token"}), 400

    try:
        #verify token with Google
        idinfo = id_token.verify_oauth2_token(
            token,
            grequests.Request(),
            GOOGLE_CLIENT_ID
        )

        email = idinfo["email"]

    except ValueError:
        return jsonify({"error": "Invalid token"}), 401

    # check if email is allowed in database
    user = db.session.query(UserAccount)\
        .join(Volunteer, Volunteer.id == UserAccount.volunteer_id)\
        .filter(Volunteer.email == email)\
        .first()

    if not user:
        return jsonify({"error": "Unauthorized"}), 403

    # create a login session
    session["user_id"] = user.user_id
    session["role"] = user.role
    session["email"] = email

    return jsonify({"success": True})

@app.route("/debug/absent-id")
def get_absent_id():
    absent = Station.query.filter_by(station_name="Absent").first()
    return {"absent_id": absent.station_id if absent else None}

@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    return jsonify({
        "email": session["email"],
        "role": session["role"]
    })
    
@app.route("/admin")
def admin_page():
    if "user_id" not in session:
        return redirect("/")
    return render_template("admin.html")

@app.route("/admin/master-list")
def master_list():
    volunteers = Volunteer.query.filter_by(deleted_at = None).order_by(Volunteer.last_name).all()
    return render_template("master-list.html", volunteers=volunteers)
    

@app.route("/admin/master-list/add-volunteer", methods=["POST"])
def add_volunteer():
    if "user_id" not in session:
        return redirect("/")
    
    first_name = request.form.get("first_name").strip()
    last_name = request.form.get("last_name").strip()
    email = request.form.get("email").strip().lower()

    existing = Volunteer.query.filter_by(email=email).first()
    if existing:
        flash("Volunteer with that email already exists.")
        return redirect("/admin/master-list")

    new_volunteer = Volunteer(
        first_name=first_name,
        last_name=last_name,
        email=email
    )

    db.session.add(new_volunteer)
    db.session.commit()
    grant_drive_access(new_volunteer.email)
    return redirect("/admin/master-list")

#soft deleting a user
@app.route("/admin/master-list/delete-volunteer/<int:volunteer_id>", methods=["POST"])
def delete_volunteer(volunteer_id):
    if "user_id" not in session:
        return redirect("/")

    volunteer = Volunteer.query.get_or_404(volunteer_id)
    volunteer.soft_delete()
    db.session.commit()

    return redirect("/admin/master-list")

# Adding route to new volunteer hours page
@app.route("/admin/volunteer-hours")
def volunteer_hours():
    # Get all volunteers
    volunteers = Volunteer.query.order_by(Volunteer.last_name).all()
    
    volunteer_data = []
    for v in volunteers:
        # If you don’t have an Availability table, just use v.availability
        # For now, fallback to empty string if None
        availability_text = getattr(v, "availability", "") or ""
        volunteer_data.append({
            "name": f"{v.first_name} {v.last_name}",
            "email": v.email,
            "availability": availability_text
        })
    
    return render_template("volunteer-hours.html", volunteer_data=volunteer_data)
    
@app.route("/seed-admin")
def seed_admin():
    
    email = "anthonyb@southwestern.edu"   # must match Google email
    first_name = "Barbara"
    last_name = "Anthony"
    
    volunteer = Volunteer.query.filter_by(email=email).first()
    if not volunteer:
        volunteer = Volunteer(
            first_name= first_name,
            last_name= last_name,
            email=email
        )
        db.session.add(volunteer)
        db.session.commit()

    #checking if account already exists
    existing = UserAccount.query.filter_by(volunteer_id=volunteer.id).first()

    if existing:
        return "User already exists."

    admin = UserAccount(
        volunteer_id = volunteer.id,
        password = "testing",
        role="admin"
    )

    db.session.add(admin)
    db.session.commit()

    return "Admin user created."



import json
import gspread
from google.oauth2.service_account import Credentials

def get_sheet():
    creds_dict = json.loads(os.environ["GOOGLE_SERVICE_JSON"])

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly", 
             "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    client = gspread.authorize(credentials)
    sheet = client.open("Volunteer Information - new").sheet1
    return sheet


def get_drive_service():
    creds_dict = json.loads(os.environ["GOOGLE_DRIVE_JSON"])

    scopes = ["https://www.googleapis.com/auth/drive"]

    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=scopes
    )

    service = build("drive", "v3", credentials=credentials)

    return service

DRIVE_FOLDER_ID = "1IwmKyFWKEvAB86WKg9I7C9N1BBvrSzD-"

def grant_drive_access(email):
    service = get_drive_service()

    permission = {
        "type": "user",
        "role": "reader",
        "emailAddress": email
    }

    try:
        service.permissions().create(
            fileId=DRIVE_FOLDER_ID,
            body=permission,
            sendNotificationEmail=False
        ).execute()
    except Exception as e:
        print(f"Drive permission error for {email}: {e}")

    
@app.route("/admin/sync-volunteers", methods=["POST"])
def sync_volunteers():
    if "user_id" not in session:
        return redirect("/")
    
    sheet = get_sheet()
    rows = sheet.get_all_records()

    for row in rows:
        email = row["Email (enter N/A) if you do not have one"].strip()

        volunteer = Volunteer.query.filter_by(email=email, deleted_at=None).first()

        if not volunteer:
            volunteer = Volunteer(
                first_name = row["First Name"],
                last_name = row["Last Name"],
                email = email
            )
            db.session.add(volunteer)
    db.session.commit()


    # Trying to get the hours added to the data table
    for row in rows:
        email = row["Email (enter N/A) if you do not have one"].strip()
        volunteer = Volunteer.query.filter_by(email=email).first()
        if not volunteer:
            continue  # just in case

        # Remove old availability so we don’t duplicate
        Availability.query.filter_by(volunteer_id=volunteer.id).delete()

        availability_text = str(row.get("What is your typical shift? Select all hours that you work from when you come in until you leave. (Ex. if you work 11-2, you would select 11AM, 12PM, 1PM, 2PM)", ""))
        entries = availability_text.split(",")

        for entry in entries:
            time_str = entry.strip().upper()
            if not time_str:
                continue

            # convert AM/PM text to numeric hour
            if "AM" in time_str:
                hour = int(time_str.replace("AM", ""))
            elif "PM" in time_str:
                hour = int(time_str.replace("PM", ""))
                if hour != 12:
                    hour += 12
            else:
                continue

            new_availability = Availability(
                volunteer_id=volunteer.id,
                hour=hour
            )
            db.session.add(new_availability)

    db.session.commit()  # commit the new availability rows

    return redirect("/admin/master-list")
    
#attempting to write a flask cli command to add admins
import click
from flask.cli import with_appcontext

@app.cli.command("create-admin")
@click.argument("email")
@click.argument("first_name")
@click.argument("last_name")
@with_appcontext

def create_admin(email, first_name, last_name):
    volunteer = Volunteer.query.filter_by(email=email).first()

    if not volunteer:
        volunteer = Volunteer(
            first_name=first_name,
            last_name=last_name,
            email=email
        )
        db.session.add(volunteer)
        db.session.flush() #adds without actually committing so we can get ID

    existing = UserAccount.query.filter_by(volunteer_id=volunteer.id).first()

    if existing: 
        click.echo("User already has an account")
        return
    admin = UserAccount(
        volunteer_id=volunteer.id,
        password="stilltesting",
        role="admin"
    )
    db.session.add(admin)


    db.session.commit()

    click.echo(f"admin privileges given to {email}")

