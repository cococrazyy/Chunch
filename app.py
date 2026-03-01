from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String
from sqlalchemy import Column, Integer, String, Enum, Date, Time
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import ForeignKey
import os
from flask import request, jsonify, session, redirect, url_for
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from werkzeug.middleware.proxy_fix import ProxyFix

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

#render sometimes gives postgres://, sqlalchemy needs postgresql://
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# creating a volunteer class
#class Volunteer(db.Model, SoftDeleteMixin):
class Volunteer(db.Model):

    __tablename__ = "volunteers"

    id = Column(Integer, primary_key=True)

    first_name = Column(String(50))
    last_name = Column(String(50))

    email = Column(String(100), unique=True)
# creating user account class
# only admins and captains should have be on this table
class UserAccount(db.Model):
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
class Station(db.Model):
    __tablename__ = "station"
    station_id = Column(Integer, primary_key=True)

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
class Schedule(db.Model):
    __tablename__ = "schedule"
    schedule_id = Column(Integer, primary_key=True)
    date = Column(Date)
    time = Column(Time)

# creating assignment table
class Assignment(db.Model):
    __tablename__ = "assignments"
    assignment_id = Column(Integer, primary_key=True)
    
    volunteer_id = Column(Integer, ForeignKey("volunteers.id"))
    station_id = Column(Integer, ForeignKey("station.station_id"))
    schedule_id = Column(Integer, ForeignKey("schedule.schedule_id"))
    
    created_by = Column(Integer, ForeignKey("user_account.user_id"))

    volunteer = relationship("Volunteer", backref = "assignments")
    station = relationship("Station", backref = "assignments")
    schedule = relationship("Schedule", backref = "assignments")


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

    return send_from_directory(".", "admin.html")
def volunteer_list():
    volunteers = Volunteer.query.order_by(Volunteer.last_name).all()
    return render_template("admin.html", volunteers=volunteers)

@app.route("/seed-admin")
def seed_admin():
    
    email = "agarza6044@gmail.com"   # must match Google email
    first_name = "Aaron"
    last_name = "Garza"
    
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
    sheet = client.open("Chunch Volunteer Info").sheet1
    return sheet

    
@app.route("/api/sync-volunteers")
def sync_volunteers():
    sheet = get_sheet()
    rows = sheet.get_all_records()

    added = 0

    for row in rows:
        email = row["Email"].strip()

        volunteer = Volunteer.query.filter_by(email=email).first()

        if not volunteer:
            volunteer = Volunteer(
                first_name = row["First Name"],
                last_name = row["Last Name"],
                email = email
            )
            db.session.add(volunteer)
            added += 1
    db.session.commit()

    return {
        "status": "success", 
        "added": added
    }
    
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

