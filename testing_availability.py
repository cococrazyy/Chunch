from app import db, Volunteer, Availability, app

with app.app_context():
    v = Volunteer.query.first()
    print(v.first_name, v.last_name)
    if v.availability:
        print(v.availability[0].hour)  # only first hour
    else:
        print("No availability")