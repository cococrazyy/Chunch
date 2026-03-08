# testing_availability.py
from app import app, db, Volunteer, Availability

# Use application context to access Flask/SQLAlchemy
with app.app_context():
    # Create all tables if they don't exist
    db.create_all()

    # Check if there is already at least one volunteer
    volunteer = Volunteer.query.first()
    if not volunteer:
        # Create a test volunteer
        volunteer = Volunteer(
            first_name="Test",
            last_name="User",
            email="testuser@example.com"
        )
        db.session.add(volunteer)
        db.session.commit()
        print("Created test volunteer.")

    # Add some availability for this volunteer
    if not volunteer.availability:
        slots = [8, 9, 10]  # example hours
        for hour in slots:
            availability = Availability(
                volunteer_id=volunteer.id,
                hour=hour,
                day="Monday"
            )
            db.session.add(availability)
        db.session.commit()
        print("Added availability for volunteer.")

    # Print all volunteers and their availability
    print("\nVolunteers and their availability:")
    for v in Volunteer.query.order_by(Volunteer.last_name).all():
        print(f"{v.first_name} {v.last_name}:")
        if v.availability:
            for slot in v.availability:
                print(f"  - {slot.day} at {slot.hour}:00")
        else:
            print("  - No availability recorded.")