from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String
from sqlalchemy import Column, Integer, String, Enum, Date, Time, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, backref
import os
from flask import request, jsonify, session, redirect, url_for, flash
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import render_template
from googleapiclient.discovery import build
from flask_softdelete import SoftDeleteMixin
from flask_migrate import Migrate
from datetime import date
from sqlalchemy import text
from flask import render_template

app = Flask(__name__, static_folder='.', static_url_path='')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
is_production = os.environ.get("RENDER") == "true"
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
    phone = Column(String(100), unique=True)
    #station_id = Column(Integer, ForeignKey("station.station_id"))
    #station = relationship("Station")

#for people signing up to volunteer that will be placed in inbox
class Applicant(db.Model, SoftDeleteMixin):
    __tablename__ = "applicants"

    id = Column(Integer, primary_key=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    email = Column(String(50))
    phone = Column(String(50))
    status = Column(
        Enum(
            "accepted",
            "rejected",
            "pending",
            name="status_enum"
        ), nullable=False, default="pending"
    )
    availability = Column(String(500))
    unavailability = Column(String(500))
    
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

class Absence(db.Model):
    __tablename__ = "absences"

    absence_id = Column(Integer, primary_key=True)

    volunteer_id = Column(Integer, ForeignKey("volunteers.id"), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    is_partial = Column(Boolean, nullable=False, default=False)

    partial_start_hour = Column(Integer, nullable=True)
    partial_end_hour = Column(Integer, nullable=True)

    notes = Column(String(255), nullable=True)

    volunteer = relationship("Volunteer", backref="absences")

# creating schedule table
class Schedule(db.Model, SoftDeleteMixin):
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

    is_absent = Column(Boolean, default=False)
    is_covering = Column(Boolean, default=False, nullable=False)
    covering_for_volunteer_id = Column(Integer, ForeignKey("volunteers.id"), nullable=True)
    original_station_id = Column(Integer, ForeignKey("station.station_id"), nullable=True)
    absence_id = Column(Integer, ForeignKey("absences.absence_id"), nullable=True)

    volunteer = relationship("Volunteer", foreign_keys=[volunteer_id])
    station = relationship("Station", foreign_keys=[station_id])
    schedule = relationship("Schedule", backref="assignments")

# creating a class that will store the availiablity hours for each person
class Availability(db.Model, SoftDeleteMixin):
    __tablename__ = "availability"

    availability_id = Column(Integer, primary_key=True)

    volunteer_id = Column(Integer, ForeignKey("volunteers.id"))

    hour = Column(String(50))       # Example: 8, 9, 10, 11

    volunteer = relationship("Volunteer", backref=backref("availability", cascade = "all, delete-orphan"))

with app.app_context():
    db.create_all()

    db.session.execute(text("""
        ALTER TABLE assignments
        ADD COLUMN IF NOT EXISTS is_covering BOOLEAN NOT NULL DEFAULT FALSE
    """))

    db.session.execute(text("""
        ALTER TABLE assignments
        ADD COLUMN IF NOT EXISTS covering_for_volunteer_id INTEGER
    """))

    db.session.execute(text("""
        ALTER TABLE assignments
        ADD COLUMN IF NOT EXISTS original_station_id INTEGER
    """))

    db.session.execute(text("""
        ALTER TABLE assignments
        ADD COLUMN IF NOT EXISTS absence_id INTEGER
    """))

    db.session.commit()
        
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

@app.route("/admin/edit-volunteer", methods=["POST"])
def edit_volunteer():
    data = request.get_json()

    volunteer = Volunteer.query.get_or_404(data["id"])
    
    volunteer.first_name = data.get("first_name")
    volunteer.last_name = data.get("last_name")
    volunteer.email = data.get("email")
    volunteer.phone = data.get("phone")

    db.session.commit()

    return {"success": True}
    
@app.route("/admin")
def admin_page():
    try:
        debug_admin = request.args.get("debug_admin") == "1"

        if "user_id" not in session and not debug_admin:
            return redirect("/")

        volunteers = Volunteer.query\
            .filter(Volunteer.deleted_at.is_(None))\
            .order_by(Volunteer.last_name)\
            .all()

        return render_template("admin.html", volunteers=volunteers)

    except Exception as e:
        return f"<pre>{type(e).__name__}: {str(e)}</pre>", 500

@app.route("/admin/coverage/details")
def coverage_details():
    volunteer_id = request.args.get("volunteer_id", type=int)

    if not volunteer_id:
        return {"error": "Missing volunteer_id"}, 400

    absent_volunteer = Volunteer.query\
        .filter(Volunteer.deleted_at.is_(None), Volunteer.id == volunteer_id)\
        .first()

    if not absent_volunteer:
        return {"error": "Volunteer not found"}, 404

    latest_absence = Absence.query\
        .filter(Absence.volunteer_id == volunteer_id)\
        .order_by(Absence.absence_id.desc())\
        .first()

    if not latest_absence:
        return "<pre>No absence record found for this volunteer.</pre>", 404

    sheet = get_sheet()
    rows = sheet.get_all_records()

    row_by_email = {}
    for row in rows:
        email = str(row.get("Email", "")).strip().lower()
        if email:
            row_by_email[email] = row

    absent_email = (absent_volunteer.email or "").strip().lower()
    absent_row = row_by_email.get(absent_email)

    if not absent_row:
        return {"error": "Absent volunteer not found in sheet"}, 404

    def parse_time_to_hour(time_str):
        time_str = str(time_str).strip().upper().replace(" ", "")

        if not time_str:
            return None

        if time_str.endswith("AM"):
            raw = time_str[:-2]
            if ":" in raw:
                raw = raw.split(":")[0]
            if not raw.isdigit():
                return None
            hour = int(raw)
            return 0 if hour == 12 else hour

        if time_str.endswith("PM"):
            raw = time_str[:-2]
            if ":" in raw:
                raw = raw.split(":")[0]
            if not raw.isdigit():
                return None
            hour = int(raw)
            return hour if hour == 12 else hour + 12

        return None

    def parse_hour_list(text):
        text = str(text).strip()
        if not text:
            return []

        normalized = text.replace("–", "-").replace("—", "-")
        parts = [part.strip() for part in normalized.split(",") if part.strip()]

        hours = set()

        for part in parts:
            if "-" in part:
                start_str, end_str = part.split("-", 1)
                start_hour = parse_time_to_hour(start_str)
                end_hour = parse_time_to_hour(end_str)

                if start_hour is None or end_hour is None:
                    continue

                if start_hour > end_hour:
                    continue

                for hour in range(start_hour, end_hour + 1):
                    hours.add(hour)
            else:
                single_hour = parse_time_to_hour(part)
                if single_hour is not None:
                    hours.add(single_hour)

        return sorted(hours)

    def format_hour(h):
        if h == 0:
            return "12AM"
        elif h < 12:
            return f"{h}AM"
        elif h == 12:
            return "12PM"
        else:
            return f"{h-12}PM"

    def build_ranges(hours):
        if not hours:
            return []

        ranges = []
        start = hours[0]
        prev = hours[0]

        for h in hours[1:]:
            if h == prev + 1:
                prev = h
            else:
                ranges.append((start, prev))
                start = h
                prev = h

        ranges.append((start, prev))
        return ranges

    def format_ranges(hours):
        ranges = build_ranges(hours)

        return ", ".join(
            f"{format_hour(start)}–{format_hour(end)}"
            for start, end in ranges
        )

    typical_shift = str(absent_row.get("Typical Shift", "")).strip()
    full_shift_hours = parse_hour_list(typical_shift)

    if latest_absence.is_partial:
        shift_hours = list(range(
            latest_absence.partial_start_hour,
            latest_absence.partial_end_hour + 1
        ))
        shift_label = format_ranges(shift_hours)
    else:
        shift_hours = full_shift_hours
        shift_label = typical_shift

    shift_hour_set = set(shift_hours)
    shift_length = len(shift_hours)

    fully_available_reserves = []
    partial_overlap_reserves = []

    volunteer_by_email = {
        (v.email or "").strip().lower(): v
        for v in Volunteer.query
            .filter(Volunteer.deleted_at.is_(None))
            .all()
        if v.email
    }

    reserve_station = Station.query.filter_by(station_name="Reserve").first()
    reserve_station_id = reserve_station.station_id if reserve_station else None

    for row in rows:
        email = str(row.get("Email", "")).strip().lower()
        typical_station = str(row.get("Typical Station", "")).strip().lower()

        if not email or typical_station != "reserve":
            continue

        volunteer = volunteer_by_email.get(email)
        if not volunteer:
            continue

        latest_assignment = Assignment.query.filter_by(
            volunteer_id=volunteer.id
        ).order_by(
            Assignment.assignment_id.desc()
        ).first()

        if latest_assignment and reserve_station_id is not None:
            if latest_assignment.station_id != reserve_station_id:
                continue

        unavailability_text = str(row.get("Unavailability", "")).strip()
        unavailable_hours = parse_hour_list(unavailability_text)
        unavailable_hour_set = set(unavailable_hours)

        overlapping_hours = sorted(shift_hour_set.intersection(unavailable_hour_set))
        overlap_count = len(overlapping_hours)

        reserve_info = {
            "id": volunteer.id,
            "name": f"{volunteer.first_name} {volunteer.last_name}",
            "email": volunteer.email,
            "phone": volunteer.phone,
            "typical_shift": str(row.get("Typical Shift", "")).strip(),
            "unavailability": unavailability_text,
            "overlapping_label": format_ranges(overlapping_hours),
            "special_notes": str(row.get("Special Notes", "")).strip()
        }

        if overlap_count == 0:
            fully_available_reserves.append(reserve_info)
        elif shift_length > 0 and (overlap_count / shift_length) < 0.5:
            partial_overlap_reserves.append(reserve_info)
    absent_assignment = Assignment.query.filter_by(
        volunteer_id=absent_volunteer.id
    ).first()

    station_name = ""
    if absent_assignment and absent_assignment.station:
        station_name = str(absent_assignment.station.station_name)

    return render_template(
        "coverage-details.html",
        absent_volunteer={
            "id": absent_volunteer.id,
            "absence_id": latest_absence.absence_id,
            "name": f"{absent_volunteer.first_name} {absent_volunteer.last_name}",
            "email": absent_volunteer.email,
            "station_name": station_name,
            "typical_shift": shift_label,
            "unavailability": str(absent_row.get("Unavailability", "")).strip(),
            "start_date": latest_absence.start_date,
            "end_date": latest_absence.end_date,
            "is_partial": latest_absence.is_partial,
            "notes": latest_absence.notes or ""
        },
        fully_available_reserves=fully_available_reserves,
        partial_overlap_reserves=partial_overlap_reserves
    )

@app.route("/debug/reset-all-covering")
def reset_all_covering():
    try:
        reserve_station = Station.query.filter_by(station_name="Reserve").first()
        if not reserve_station:
            return {"error": "Reserve station not found"}, 404

        covering_assignments = Assignment.query\
            .filter_by(is_covering=True)\
            .all()

        reset_count = 0

        for assignment in covering_assignments:
            assignment.station_id = reserve_station.station_id
            assignment.is_covering = False
            assignment.covering_for_volunteer_id = None
            assignment.original_station_id = None
            assignment.absence_id = None
            reset_count += 1

        db.session.commit()

        return {
            "success": True,
            "message": "All covering volunteers moved back to Reserve",
            "reset_count": reset_count
        }

    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}, 500

@app.route("/admin/absence/update", methods=["POST"])
def update_absence():
    data = request.get_json()

    volunteer_id = data.get("volunteer_id")
    action = data.get("action")
    mode = data.get("mode")
    new_end_date = data.get("new_end_date")

    absence = Absence.query.filter_by(volunteer_id=volunteer_id).first()
    if not absence:
        return jsonify({"error": "Absence not found"}), 404

    assignment = Assignment.query.filter_by(
        volunteer_id=volunteer_id,
        schedule_id=None
    ).first()

    reserve_assignment = Assignment.query.filter_by(
        covering_for_volunteer_id=volunteer_id
    ).first()

    if mode == "end":

        if action == "move_now":
            if reserve_assignment:
                reserve_assignment.station_id = reserve_assignment.original_station_id
                reserve_assignment.is_covering = False
                reserve_assignment.covering_for_volunteer_id = None
                reserve_assignment.original_station_id = None
                reserve_assignment.absence_id = None

        if assignment:
            assignment.is_absent = False

        db.session.delete(absence)

    elif mode == "shorten":

        if not new_end_date:
            return jsonify({"error": "Missing new end date"}), 400

        absence.end_date = new_end_date

        if action == "move_now":
            # reserve leaves EARLY (on new date)
            if reserve_assignment:
                reserve_assignment.station_id = reserve_assignment.original_station_id
                reserve_assignment.is_covering = False
                reserve_assignment.covering_for_volunteer_id = None
                reserve_assignment.original_station_id = None
                reserve_assignment.absence_id = None

        elif action == "double_coverage":
            pass

    db.session.commit()

    return jsonify({"success": True})

@app.route("/admin/coverage/assign", methods=["POST"])
def assign_reserve_coverage():
    try:
        if "user_id" not in session:
            return redirect("/")

        absence_id = request.form.get("absence_id", type=int)
        absent_volunteer_id = request.form.get("absent_volunteer_id", type=int)
        reserve_volunteer_id = request.form.get("reserve_volunteer_id", type=int)

        if not absence_id or not absent_volunteer_id or not reserve_volunteer_id:
            return "<pre>Missing required coverage fields.</pre>", 400

        if absent_volunteer_id == reserve_volunteer_id:
            return "<pre>A volunteer cannot cover their own absence.</pre>", 400

        absence = Absence.query.get(absence_id)
        if not absence:
            return "<pre>Absence record not found.</pre>", 404

        absent_assignment = Assignment.query.filter_by(
            volunteer_id=absent_volunteer_id
        ).first()

        if not absent_assignment:
            absent_volunteer = Volunteer.query.get(absent_volunteer_id)
            if not absent_volunteer:
                return "<pre>Absent volunteer not found.</pre>", 404

            sheet = get_sheet()
            rows = sheet.get_all_records()

            absent_row = None
            absent_email = (absent_volunteer.email or "").strip().lower()

            for row in rows:
                row_email = str(row.get("Email", "")).strip().lower()
                if row_email == absent_email:
                    absent_row = row
                    break

            if not absent_row:
                return "<pre>Absent volunteer assignment not found and volunteer is not in the sheet.</pre>", 404

            typical_station_name = str(absent_row.get("Typical Station", "")).strip()

            if not typical_station_name:
                return "<pre>Absent volunteer has no typical station in the sheet.</pre>", 404

            station = Station.query.filter_by(station_name=typical_station_name).first()
            if not station:
                return f"<pre>Station '{typical_station_name}' not found.</pre>", 404

            absent_assignment = Assignment(
                volunteer_id=absent_volunteer_id,
                station_id=station.station_id,
                schedule_id=None
            )
            db.session.add(absent_assignment)
            db.session.flush()
        reserve_assignment = Assignment.query.filter_by(
            volunteer_id=reserve_volunteer_id
        ).first()

        reserve_station = Station.query.filter_by(station_name="Reserve").first()
        if not reserve_station:
            return "<pre>Reserve station not found.</pre>", 404

        if not reserve_assignment:
            reserve_assignment = Assignment(
                volunteer_id=reserve_volunteer_id,
                station_id=reserve_station.station_id,
                schedule_id=None
            )
            db.session.add(reserve_assignment)
            db.session.flush()
        if reserve_assignment.station_id != reserve_station.station_id:
            return "<pre>Selected volunteer is not currently in the reserve pool.</pre>", 400

        absent_assignment.is_absent = True

        reserve_assignment.original_station_id = reserve_assignment.station_id
        reserve_assignment.station_id = absent_assignment.station_id
        reserve_assignment.is_covering = True
        reserve_assignment.covering_for_volunteer_id = absent_volunteer_id
        reserve_assignment.absence_id = absence_id

        db.session.commit()

        return redirect("/admin")

    except Exception as e:
        db.session.rollback()
        return f"<pre>{type(e).__name__}: {str(e)}</pre>", 500

@app.route("/admin/need-coverage/save", methods=["POST"])
def save_need_coverage():
    try:
        if "user_id" not in session:
            return redirect("/")

        volunteer_id = request.form.get("volunteer_id", type=int)
        start_date_str = request.form.get("start_date", "").strip()
        end_date_str = request.form.get("end_date", "").strip()
        is_partial_str = request.form.get("is_partial", "false").strip().lower()
        partial_start_hour = request.form.get("partial_start_hour", type=int)
        partial_end_hour = request.form.get("partial_end_hour", type=int)
        notes = request.form.get("notes", "").strip()

        if not volunteer_id or not start_date_str or not end_date_str:
            return "<pre>Missing required fields.</pre>", 400

        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)

        if end_date < start_date:
            return "<pre>End date cannot be before start date.</pre>", 400

        is_partial = (is_partial_str == "true")

        if is_partial:
            if partial_start_hour is None or partial_end_hour is None:
                return "<pre>Partial absences require both start and end hours.</pre>", 400

            if partial_start_hour > partial_end_hour:
                return "<pre>Partial start hour cannot be after partial end hour.</pre>", 400
        else:
            partial_start_hour = None
            partial_end_hour = None

        absence = Absence(
            volunteer_id=volunteer_id,
            start_date=start_date,
            end_date=end_date,
            is_partial=is_partial,
            partial_start_hour=partial_start_hour,
            partial_end_hour=partial_end_hour,
            notes=notes or None
        )

        db.session.add(absence)
        db.session.commit()

        return redirect(f"/admin/coverage/details?volunteer_id={volunteer_id}")

    except Exception as e:
        db.session.rollback()
        return f"<pre>{type(e).__name__}: {str(e)}</pre>", 500

#     s = Station.query.filter_by(station_name="Line Servers").first()

#     volunteers = Volunteer.query\
#         .filter(Volunteer.deleted_at.is_(None))\
#         .order_by(Volunteer.id)\
#         .all()

#     v = None
#     for volunteer in volunteers:
#         valid_hours = []
#         for a in volunteer.availability:
#             if a.deleted_at is not None:
#                 continue
#             try:
#                 hour = int(str(a.hour).strip())
#             except (ValueError, TypeError):
#                 continue
#             if 5 <= hour <= 16:
#                 valid_hours.append(hour)

#         if valid_hours:
#             v = volunteer
#             break

#     if not v or not s:
#         return "Missing volunteer with hours or station"

#     existing = Assignment.query.filter_by(
#         volunteer_id=v.id,
#         station_id=s.station_id,
#         schedule_id=None
#     ).first()

#     if existing:
#         return {
#             "message": "Assignment already exists",
#             "volunteer": v.id,
#             "station": s.station_id
#         }

#     assignment = Assignment(
#         volunteer_id=v.id,
#         station_id=s.station_id,
#         schedule_id=None
#     )

#     db.session.add(assignment)
#     db.session.commit()

#     return {
#         "message": "Assignment added",
#         "volunteer": v.id,
#         "station": s.station_id
#     }

# Delete assignments based on assignment number
#@app.route("/debug/delete-assignment/<int:assignment_id>/get")
#def delete_assignment(assignment_id):
    #assignment = Assignment.query.get(assignment_id)
    #if not assignment:
        #return {"error": f"Assignment {assignment_id} not found"}, 404

    #db.session.delete(assignment)
    #db.session.commit()
    #return {"message": f"Assignment {assignment_id} deleted"}

# Delete assignments based on volunteer id
#@app.route("/debug/delete-assignments-for-volunteer/<int:volunteer_id>", methods=["POST"])
#def delete_assignments_for_volunteer(volunteer_id):
#    assignments = Assignment.query.filter_by(volunteer_id=volunteer_id).all()
#    if not assignments:
#        return {"message": "No assignments to delete"}, 404
#
#    for a in assignments:
#        db.session.delete(a)
#
#    db.session.commit()
#    return {"message": f"Deleted {len(assignments)} assignments for volunteer {volunteer_id}"}

@app.route("/admin/debug-hourly-final")
def debug_hourly_final():
    try:
        volunteers = Volunteer.query\
            .filter(Volunteer.deleted_at.is_(None))\
            .order_by(Volunteer.last_name, Volunteer.first_name)\
            .all()

        stations = Station.query\
            .filter(Station.station_name != "Other")\
            .order_by(Station.station_name)\
            .all()

        accounts = UserAccount.query.all()
        role_by_volunteer_id = {
            account.volunteer_id: account.role
            for account in accounts
            if account.volunteer_id is not None
        }

        sheet = get_sheet()
        rows = sheet.get_all_records()

        sheet_row_by_email = {}
        for row in rows:
            email = str(row.get("Email", "")).strip().lower()
            if email:
                sheet_row_by_email[email] = row

        volunteer_rows_by_id = {}

        for v in volunteers:
            captain_status = "Volunteer"
            if role_by_volunteer_id.get(v.id) == "captain":
                captain_status = "Captain"

            email_key = v.email.strip().lower() if v.email else ""
            sheet_row = sheet_row_by_email.get(email_key, {})

            latest_absence = Absence.query\
                .filter(Absence.volunteer_id == v.id)\
                .order_by(Absence.absence_id.desc())\
                .first()

            volunteer_rows_by_id[v.id] = {
                "id": v.id,
                "name": f"{v.first_name} {v.last_name}",
                "email": v.email or "",
                "phone": v.phone or "",
                "captain_status": captain_status,
                "typical_shift": str(sheet_row.get("Typical Shift", "")).strip(),
                "unavailability": str(sheet_row.get("Unavailability", "")).strip(),
                "capability_restrictions": str(
                    sheet_row.get("Capability Restrictions", "") or
                    sheet_row.get("Restrictions", "") or
                    sheet_row.get("Other Info", "")
                ).strip(),
                "absence_id": latest_absence.absence_id if latest_absence else None,
                "absence_start_date": latest_absence.start_date.isoformat() if latest_absence and latest_absence.start_date else "",
                "absence_end_date": latest_absence.end_date.isoformat() if latest_absence and latest_absence.end_date else "",
                "absence_is_partial": latest_absence.is_partial if latest_absence else False,
                "absence_partial_start_hour": latest_absence.partial_start_hour if latest_absence else None,
                "absence_partial_end_hour": latest_absence.partial_end_hour if latest_absence else None,
                "absence_notes": latest_absence.notes or "" if latest_absence else ""
            }

        station_to_volunteer_ids = {
            station.station_id: set()
            for station in stations
        }

        station_name_to_id = {
            str(station.station_name).strip().lower(): station.station_id
            for station in stations
        }

        volunteer_id_by_email = {
            v.email.strip().lower(): v.id
            for v in volunteers
            if v.email
        }

        for row in rows:
            email = str(row.get("Email", "")).strip().lower()
            typical_station = str(row.get("Typical Station", "")).strip().lower()

            if not email or not typical_station or typical_station == "other":
                continue

            volunteer_id = volunteer_id_by_email.get(email)
            station_id = station_name_to_id.get(typical_station)

            if volunteer_id is None or station_id is None:
                continue

            station_to_volunteer_ids[station_id].add(volunteer_id)

        absent_station = Station.query.filter_by(station_name="Absent").first()
        absent_station_id = absent_station.station_id if absent_station else None

        today = date.today()

        assignments = Assignment.query.all()

        for assignment in assignments:
            if assignment.is_covering and assignment.absence_id:
                absence = Absence.query.get(assignment.absence_id)
                if absence and absence.end_date < today:
                    if assignment.original_station_id is not None:
                        assignment.station_id = assignment.original_station_id

                    assignment.is_covering = False
                    assignment.covering_for_volunteer_id = None
                    assignment.original_station_id = None
                    assignment.absence_id = None

                    covered = Assignment.query.filter_by(
                        volunteer_id=absence.volunteer_id
                    ).first()

                    if covered:
                        covered.is_absent = False

        db.session.commit()   

        for assignment in assignments:
            if assignment.volunteer_id is None:
                continue

            for volunteer_ids in station_to_volunteer_ids.values():
                volunteer_ids.discard(assignment.volunteer_id)

            if assignment.is_absent and absent_station_id is not None:
                station_to_volunteer_ids[absent_station_id].add(assignment.volunteer_id)
            elif assignment.station_id is not None:
                station_to_volunteer_ids.setdefault(
                    assignment.station_id, set()
                ).add(assignment.volunteer_id)
        station_data = {}

        for station in stations:
            station_name = str(station.station_name)
            assigned_ids = station_to_volunteer_ids.get(station.station_id, set())

            volunteers_for_station = [
                volunteer_rows_by_id[vid]
                for vid in assigned_ids
                if vid in volunteer_rows_by_id
            ]

            volunteers_for_station.sort(key=lambda x: x["name"])

            station_data[station_name] = {
                "volunteers": volunteers_for_station
            }

        return station_data

    except Exception as e:
        return {"error": str(e)}, 500

@app.route("/admin/debug-other-check")
def debug_other_check():
    volunteers = Volunteer.query\
        .filter(Volunteer.deleted_at.is_(None))\
        .order_by(Volunteer.id)\
        .all()

    assignments = Assignment.query\
        .order_by(Assignment.assignment_id.asc())\
        .all()

    latest_station_by_volunteer = {}
    for assignment in assignments:
        if assignment.station_id is None or assignment.volunteer_id is None:
            continue
        latest_station_by_volunteer[assignment.volunteer_id] = assignment.station_id

    assigned_volunteer_ids = set(latest_station_by_volunteer.keys())

    return {
        "assigned_volunteer_ids": list(assigned_volunteer_ids),
        "volunteer_rows_by_id_keys": [v.id for v in volunteers],
        "sample_pairs": [
            {
                "volunteer_id": v.id,
                "is_assigned": v.id in assigned_volunteer_ids
            }
            for v in volunteers[:15]
        ]
    }

@app.route("/admin/debug-hourly-data")
def debug_hourly_data():
    volunteers = Volunteer.query\
        .filter(Volunteer.deleted_at.is_(None))\
        .order_by(Volunteer.last_name, Volunteer.first_name)\
        .all()

    stations = Station.query\
        .order_by(Station.station_name)\
        .all()

    def parse_hours(availability_rows):
        cleaned_hours = []

        for row in availability_rows:
            if row.deleted_at is not None:
                continue

            try:
                hour = int(str(row.hour).strip())
            except (ValueError, TypeError):
                continue

            if 5 <= hour <= 16:
                cleaned_hours.append(hour)

        return sorted(set(cleaned_hours))

    def build_ranges(hours):
        if not hours:
            return []

        ranges = []
        start = hours[0]
        prev = hours[0]

        for h in hours[1:]:
            if h == prev + 1:
                prev = h
            else:
                ranges.append([start, prev])
                start = h
                prev = h

        ranges.append([start, prev])
        return ranges

    def format_hour(h):
        if h == 0:
            return "12AM"
        elif h < 12:
            return f"{h}AM"
        elif h == 12:
            return "12PM"
        else:
            return f"{h-12}PM"

    volunteer_rows_by_id = {}
    for v in volunteers:
        hours = parse_hours(v.availability)
        ranges = build_ranges(hours)

        if ranges:
            range_label = ", ".join(
                f"{format_hour(start)}-{format_hour(end)}"
                for start, end in ranges
            )
        else:
            range_label = "N/A"

        volunteer_rows_by_id[v.id] = {
            "name": f"{v.first_name} {v.last_name}",
            "hours": hours,
            "ranges": ranges,
            "range_label": range_label
        }

    assignments = Assignment.query.all()

    station_to_volunteer_ids = {}
    for station in stations:
        station_to_volunteer_ids[station.station_id] = set()

    for assignment in assignments:
        if assignment.station_id is None or assignment.volunteer_id is None:
            continue

        station_to_volunteer_ids.setdefault(
            assignment.station_id, set()
        ).add(assignment.volunteer_id)

    station_data = {}
    for station in stations:
        station_name = str(station.station_name)
        assigned_ids = station_to_volunteer_ids.get(station.station_id, set())

        station_data[station_name] = {
            "station_id": station.station_id,
            "assigned_ids": list(assigned_ids),
            "volunteers": [
                volunteer_rows_by_id[vid]
                for vid in assigned_ids
                if vid in volunteer_rows_by_id
            ]
        }

    return station_data

@app.route("/admin/inbox")
def inbox():
    applicants = Applicant.query.filter(Applicant.status == 'pending').all()
    rejected = Applicant.query.filter(Applicant.status == 'rejected').all()

    stations = Station.query.all()
    schedules = Schedule.query.all()
    return render_template("inbox.html", applicants=applicants, rejected=rejected, 
                           stations=stations, schedules=schedules)

@app.route("/admin/inbox/accept-with-assignment", methods=["POST"])
def accept_applicant(applicants_id):
    if "user_id" not in session:
        return redirect("/")
    applicants_id = request.form.get("applicant_id")
    station_id = request.form.get("station_id")
    schedule_id = request.form.get("schedule_id")
    
    applicant = Applicant.query.get_or_404(applicants_id)
    volunteer = Volunteer(
        first_name=applicant.first_name,
        last_name=applicant.last_name,
        email=applicant.email,
        phone=applicant.phone
    )
    db.session.add(volunteer)
    db.session.flush()  
    
    assignment = Assignment(
        volunteer_id=volunteer.id,
        station_id=station_id,
        schedule_id=schedule_id
    )
    db.session.add(assignment)

    applicant.status = "accepted"
    db.session.commit()

    return redirect("/admin/inbox")

@app.route("/admin/inbox/reject/<int:applicants_id>", methods=["POST"])
def reject_applicant(applicants_id):
    if "user_id" not in session:
        return redirect("/")
    applicant = Applicant.query.get_or_404(applicants_id)
    if applicant:
        applicant.status = 'rejected'
        db.session.commit()
    return redirect("/admin/inbox")

@app.route("/admin/inbox/pending/<int:applicants_id>", methods=["POST"])
def undo_rejection(applicants_id):
    if "user_id" not in session:
        return redirect("/")
    applicant = Applicant.query.get_or_404(applicants_id)
    if applicant:
        applicant.status = 'pending'
        db.session.commit()
    return redirect("/admin/inbox")

@app.route("/admin/master-list")
def master_list():
    volunteers = Volunteer.query\
        .filter(Volunteer.deleted_at.is_(None))\
        .order_by(Volunteer.last_name)\
        .all()
    
    accounts = UserAccount.query.all()
    role_by_volunteer_id = {
        account.volunteer_id: account.role
        for account in accounts
        if account.volunteer_id is not None
    }

    volunteer_rows = []
    for v in volunteers:
        #role = role_by_volunteer_id.get(v.id, "volunteer")
        user = UserAccount.query.filter(UserAccount.volunteer_id == v.id).first() 
        volunteer_rows.append({
            "id": v.id,
            "first_name": v.first_name,
            "last_name": v.last_name,
            "email": v.email,
            "phone": v.phone,
            "captain_status": user.role if user is not None else "Volunteer"
        })

    return render_template("master-list.html", volunteers=volunteer_rows)
    

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

@app.route("/admin/master-list/deleted-volunteers")
def view_deleted():
    if "user_id" not in session:
        return redirect("/")

    deleted = Volunteer.query.filter(Volunteer.deleted_at.is_not(None))
    return render_template("deleted-volunteers.html", deleted=deleted)

@app.route("/admin/master-list/deleted-volunteers/permadelete/<int:volunteer_id>", methods=["POST"])
def perma_delete(volunteer_id):
    if "user_id" not in session:
        return redirect("/")
    volunteer = Volunteer.query.get_or_404(volunteer_id)
    if volunteer:
        db.session.delete(volunteer)
        db.session.commit()
    return redirect("/admin/master-list/deleted-volunteers")

@app.route("/admin/master-list/deleted-volunteers/undo/<int:volunteer_id>", methods=["POST"])
def undo_delete(volunteer_id):
    if "user_id" not in session:
        return redirect("/")
    volunteer = Volunteer.query.get_or_404(volunteer_id)
    if volunteer:
        volunteer.deleted_at = None
        db.session.commit()
    return redirect("/admin/master-list/deleted-volunteers")

@app.route("/student-spotlight")
def student_spotlight():
    try:
        sheet = get_spotlight_sheet()
        rows = sheet.get_all_records()

        spotlight_entries = []

        for row in rows:
            name = str(row.get("Name", "")).strip()
            year = str(row.get("Year", "")).strip()
            quote = str(row.get("Quote", "")).strip()

            if not name and not year and not quote:
                continue

            spotlight_entries.append({
                "name": name,
                "year": year,
                "quote": quote
            })

        return render_template(
            "student-spotlight.html",
            spotlight_entries=spotlight_entries
        )

    except Exception as e:
        return f"<pre>{type(e).__name__}: {str(e)}</pre>", 500
    
@app.route("/admin/debug-assignments2")
def debug_assignments():
    assignments = Assignment.query.all()
    stations = Station.query.order_by(Station.station_id).all()
    volunteers = Volunteer.query.order_by(Volunteer.id).all()

    return {
        "assignment_count": len(assignments),
        "assignments": [
            {
                "assignment_id": a.assignment_id,
                "volunteer_id": a.volunteer_id,
                "station_id": a.station_id,
                "schedule_id": a.schedule_id
            }
            for a in assignments[:50]
        ],
        "stations": [
            {
                "station_id": s.station_id,
                "station_name": str(s.station_name)
            }
            for s in stations
        ],
        "volunteers": [
            {
                "volunteer_id": v.id,
                "name": f"{v.first_name} {v.last_name}",
            }
            for v in volunteers[:50]
        ]
    }

# Adding route to new volunteer hours page
@app.route("/admin/volunteer-hours")
def volunteer_hours():
    try:
        volunteers = Volunteer.query\
            .filter(Volunteer.deleted_at.is_(None))\
            .order_by(Volunteer.last_name, Volunteer.first_name)\
            .all()

        station_names = [
            "Setup Team",
            "Teardown Team",
            "Line Servers",
            "Kitchen",
            "Drink Station",
            "Desserts",
            "Busboys/sanitation",
            "Dishwashers",
            "General Manager",
            "Greeters",
            "Baked Potato Bar",
            "Salad Bar"
        ]

        existing_station_names = {
            str(s.station_name) for s in Station.query.all()
        }

        for name in station_names:
            if name not in existing_station_names:
                db.session.add(Station(station_name=name))

        db.session.commit()

        stations = Station.query\
            .filter(Station.station_name.notin_(["Reserve", "Absent", "Other"]))\
            .order_by(Station.station_name)\
            .all()

        def parse_hours(availability_rows):
            cleaned_hours = []
            for row in availability_rows:
                if row.deleted_at is not None:
                    continue
                try:
                    hour = int(str(row.hour).strip())
                except (ValueError, TypeError):
                    continue
                if 5 <= hour <= 16:
                    cleaned_hours.append(hour)
            return sorted(set(cleaned_hours))

        def build_ranges(hours):
            if not hours:
                return []
            ranges = []
            start = hours[0]
            prev = hours[0]
            for h in hours[1:]:
                if h == prev + 1:
                    prev = h
                else:
                    ranges.append([start, prev])
                    start = h
                    prev = h
            ranges.append([start, prev])
            return ranges

        def format_hour(h):
            if h == 0:
                return "12AM"
            elif h < 12:
                return f"{h}AM"
            elif h == 12:
                return "12PM"
            else:
                return f"{h-12}PM"

        volunteer_rows_by_id = {}
        for v in volunteers:
            hours = parse_hours(v.availability)
            ranges = build_ranges(hours)

            if ranges:
                range_label = ", ".join(
                    f"{format_hour(start)}-{format_hour(end)}"
                    for start, end in ranges
                )
            else:
                range_label = "N/A"

            volunteer_rows_by_id[v.id] = {
                "name": f"{v.first_name} {v.last_name}",
                "email": v.email,
                "hours": hours,
                "ranges": ranges,
                "range_label": range_label
            }

        sheet = get_sheet()
        rows = sheet.get_all_records()

        station_to_volunteer_ids = {
            station.station_id: set()
            for station in stations
        }

        station_name_to_id = {
            str(station.station_name).strip().lower(): station.station_id
            for station in stations
        }

        volunteer_id_by_email = {
            v.email.strip().lower(): v.id
            for v in volunteers
            if v.email
        }

        for row in rows:
            email = str(row.get("Email", "")).strip().lower()
            typical_station = str(row.get("Typical Station", "")).strip().lower()

            if not email or not typical_station:
                continue

            if typical_station in {"reserve", "absent", "other"}:
                continue

            volunteer_id = volunteer_id_by_email.get(email)
            station_id = station_name_to_id.get(typical_station)

            if volunteer_id is None or station_id is None:
                continue

            station_to_volunteer_ids[station_id].add(volunteer_id)

        station_data = {}

        for station in stations:
            station_name = str(station.station_name)
            assigned_ids = station_to_volunteer_ids.get(station.station_id, set())

            station_data[station_name] = [
                volunteer_rows_by_id[vid]
                for vid in assigned_ids
                if vid in volunteer_rows_by_id
            ]

            station_data[station_name].sort(key=lambda x: x["name"])

        return render_template(
            "volunteer-hours.html",
            station_data=station_data
        )

    except Exception as e:
        return f"<pre>{type(e).__name__}: {str(e)}</pre>", 500

@app.route("/admin/debug-hourly-matches")
def debug_hourly_matches():
    volunteers = Volunteer.query\
        .filter(Volunteer.deleted_at.is_(None))\
        .order_by(Volunteer.last_name, Volunteer.first_name)\
        .all()

    sheet = get_sheet()
    rows = sheet.get_all_records()

    volunteer_id_by_email = {
        v.email.strip().lower(): {
            "id": v.id,
            "name": f"{v.first_name} {v.last_name}"
        }
        for v in volunteers
        if v.email
    }

    def parse_hours(availability_rows):
        cleaned_hours = []

        for row in availability_rows:
            if row.deleted_at is not None:
                continue
            try:
                hour = int(str(row.hour).strip())
            except (ValueError, TypeError):
                continue
            if 5 <= hour <= 16:
                cleaned_hours.append(hour)

        return sorted(set(cleaned_hours))

    output = []

    for row in rows:
        email = str(row.get("Email", "")).strip().lower()
        first_name = str(row.get("First Name", "")).strip()
        last_name = str(row.get("Last Name", "")).strip()
        typical_station = str(row.get("Typical Station", "")).strip()
        typical_shift = str(row.get("Typical Shift", "")).strip()

        matched = volunteer_id_by_email.get(email)

        if matched:
            volunteer = Volunteer.query.get(matched["id"])
            parsed_hours = parse_hours(volunteer.availability)
        else:
            parsed_hours = []

        output.append({
            "sheet_name": f"{first_name} {last_name}",
            "email": email,
            "typical_station": typical_station,
            "typical_shift": typical_shift,
            "matched_db_volunteer": matched["name"] if matched else None,
            "matched_db_id": matched["id"] if matched else None,
            "parsed_hours": parsed_hours
        })

    return {"rows": output}

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

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    spreadsheet = client.open("Chunch Volunteer Info")

    sheet = spreadsheet.worksheet("Volunteer Information")

    return sheet

def get_applicant_sheet():
    creds_dict = json.loads(os.environ["GOOGLE_SERVICE_JSON"])

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)

    client = gspread.authorize(credentials)
    spreadsheet = client.open("Chunch Volunteer Info")
    sheet = spreadsheet.worksheet("Applicants")
    return sheet

def get_spotlight_sheet():
    creds_dict = json.loads(os.environ["GOOGLE_SERVICE_JSON"])

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive"
    ]

    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(credentials)

    spreadsheet = client.open("Chunch Volunteer Info")
    sheet = spreadsheet.worksheet("Spotlight")
    return sheet

@app.route("/admin/inbox/<int:applicant_id>")
def applicant_detail(applicant_id):
    applicant = Applicant.query.get_or_404(applicant_id)
    return render_template("applicant-detail.html", applicant=applicant)

@app.route("/admin/sync-applicants", methods=["GET", "POST"])
def sync_applicants():
    if "user_id" not in session:
        return redirect("/")

    try:
        sheet = get_applicant_sheet()
        values = sheet.get_all_values()

        if len(values) < 2:
            return redirect("/admin/inbox")

        headers = values[0]
        data_rows = values[1:]

        for row in data_rows:
            row_dict = dict(zip(headers, row))

            first_name = str(row_dict.get("First Name", "")).strip()
            last_name = str(row_dict.get("Last Name", "")).strip()
            email = str(row_dict.get("Email", "")).strip().lower()
            phone = str(row_dict.get("Phone Number", "")).strip()
            member = str(row_dict.get("Member", "")).strip()
            unavailability = str(row_dict.get("Unavailability", "")).strip()
            other_info = str(row_dict.get("Other Info", "")).strip()

            if not email:
                continue

            existing = Applicant.query.filter_by(email=email).first()

            if not existing:
                applicant = Applicant(
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone=phone,
                    availability=member,
                    unavailability=unavailability,
                    status="pending"
                )
                db.session.add(applicant)
            else:
                existing.first_name = first_name
                existing.last_name = last_name
                existing.phone = phone
                existing.availability = member
                existing.unavailability = unavailability

        db.session.commit()
        return redirect("/admin/inbox")

    except Exception as e:
        db.session.rollback()
        return f"<pre>{type(e).__name__}: {str(e)}</pre>", 500

# @app.route("/admin/sync-applicants", methods=["GET", "POST"])
# def sync_applicants():
#     try:
#         if "user_id" not in session:
#             return redirect("/")

#         sheet = get_applicant_sheet()
#         rows = sheet.get_all_records()

#         for row in rows:
#             first_name = str(row.get("First Name", "")).strip()
#             last_name = str(row.get("Last Name", "")).strip()
#             email = str(row.get("Email", "")).strip().lower()
#             phone = str(row.get("Phone Number", "")).strip()

#             member = str(row.get("Member", "")).strip()
#             unavailability = str(row.get("Unavailability", "")).strip()
#             other_info = str(row.get("Other Info", "")).strip()

#             if not email:
#                 continue

#             existing = Applicant.query.filter_by(email=email).first()

#             if not existing:
#                 applicant = Applicant(
#                     first_name=first_name,
#                     last_name=last_name,
#                     email=email,
#                     phone=phone,
#                     availability=member,
#                     unavailability=unavailability,
#                     status="pending"
#                 )
#                 db.session.add(applicant)
#             else:
#                 existing.first_name = first_name
#                 existing.last_name = last_name
#                 existing.phone = phone
#                 existing.availability = member
#                 existing.unavailability = unavailability

#         db.session.commit()

#         return redirect("/admin/inbox")

#     except Exception as e:
#         db.session.rollback()
#         return f"<pre>{type(e).__name__}: {str(e)}</pre>", 500


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

    
@app.route("/admin/sync-volunteers", methods=["GET", "POST"])
def sync_volunteers():
    try:
        if "user_id" not in session:
            return redirect("/")

        sheet = get_sheet()
        rows = sheet.get_all_records()

        for row in rows:
            email = str(row.get("Email", "")).strip().lower()
            phone = str(row.get("Phone Number", "")).strip()
            if not email:
                continue
            
            volunteer = Volunteer.query.filter_by(email=email).first()

            if not volunteer:
                volunteer = Volunteer(
                    first_name=row["First Name"],
                    last_name=row["Last Name"],
                    email=email,
                    phone=phone
                )
                db.session.add(volunteer)
            if not volunteer.phone and phone:
                volunteer.phone = phone
            
        db.session.commit()

        def parse_time_to_hour(time_str):
            time_str = str(time_str).strip().upper()
            time_str = time_str.replace(" ", "")

            if not time_str:
                return None

            if time_str.endswith("AM"):
                raw = time_str[:-2]
                if ":" in raw:
                    raw = raw.split(":")[0]
                if not raw.isdigit():
                    return None
                hour = int(raw)
                return 0 if hour == 12 else hour

            if time_str.endswith("PM"):
                raw = time_str[:-2]
                if ":" in raw:
                    raw = raw.split(":")[0]
                if not raw.isdigit():
                    return None
                hour = int(raw)
                return hour if hour == 12 else hour + 12

            return None

        for row in rows:
            email = str(row.get("Email", "")).strip().lower()
            volunteer = Volunteer.query.filter_by(email=email).first()
            if not volunteer:
                continue

            Availability.query.filter_by(volunteer_id=volunteer.id).delete()

            availability_text = str(row.get("Typical Shift", "")).strip()
            if not availability_text:
                continue

            normalized_text = availability_text.replace("–", "-").replace("—", "-")
            entries = normalized_text.split(",")

            for entry in entries:
                part = entry.strip()
                if not part:
                    continue

                if "-" in part:
                    start_str, end_str = part.split("-", 1)
                    start_hour = parse_time_to_hour(start_str)
                    end_hour = parse_time_to_hour(end_str)

                    if start_hour is None or end_hour is None:
                        continue

                    if start_hour <= end_hour:
                        hours_to_add = range(start_hour, end_hour + 1)
                    else:
                        continue
                else:
                    single_hour = parse_time_to_hour(part)
                    if single_hour is None:
                        continue
                    hours_to_add = [single_hour]

                for hour in hours_to_add:
                    db.session.add(
                        Availability(
                            volunteer_id=volunteer.id,
                            hour=hour
                        )
                    )

        db.session.commit()

        return redirect("/admin/master-list")

    except Exception as e:
        db.session.rollback()
        return f"<pre>{type(e).__name__}: {str(e)}</pre>", 500
    
@app.route("/admin/need-coverage")
def need_coverage():
    if "user_id" not in session:
        return redirect("/")

    sheet = get_sheet()
    rows = sheet.get_all_records()

    non_reserve_emails = set()

    for row in rows:
        email = str(row.get("Email", "")).strip().lower()
        typical_station = str(row.get("Typical Station", "")).strip().lower()

        if email and typical_station != "reserve":
            non_reserve_emails.add(email)

    volunteers = Volunteer.query\
        .filter(Volunteer.deleted_at.is_(None))\
        .order_by(Volunteer.last_name, Volunteer.first_name)\
        .all()

    filtered_volunteers = [
        v for v in volunteers
        if (v.email or "").strip().lower() in non_reserve_emails
    ]

    return render_template("need-coverage.html", volunteers=filtered_volunteers)

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
