# classes.py

from app import db
from sqlalchemy import Column, Integer, String, Enum, Date, Time


# creating a class called user  
#class User(db.Model, SoftDeleteMixin):
class User(db.Model):
    __tablename__ = 'userinfo'

    # primary key
    id = Column(Integer, primary_key=True)

    name = Column(String(50))
    email = Column(String(50))
    phone = Column(String(50))
    station = Column(String(50))


# creating a volunteer class
#class Volunteer(db.Model, SoftDeleteMixin):
class Volunteer(db.Model):

    __tablename__ = "volunteers"

    id = Column(Integer, primary_key=True)

    first_name = Column(String(50))
    last_name = Column(String(50))

    email = Column(String(50))
    station = Column(String(50))

# creating user account class
# only admins and captains should have be on this table
class UserAccount(db.Model):
    __tablename__ = "user_account"

    user_id = Column(Integer, primary_key=True)
    volunteer_id = Column(Integer, primary_key=True)
    password = Column(String(50))
    role = Column(
        Enum(
            "admin",
            "captain",
            "volunteer",
            "other",
            name="role_enum"
        )
    ) 

# creating a stations table
class Station(db.Model):
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
    schedule_id = Column(Integer, primary_key=True)
    date = Column(Date)
    time = Column(Time)

# creating assignment table
class Assignment(db.Model):
    assignment_id = Column(Integer, primary_key=True)
    volunteer_id = Column(Integer, primary_key=True)
    station_id = Column(Integer)
    schedule_id = Column(Integer)
    created_by = Column(Integer)