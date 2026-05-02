# Chunch

This is the official GitHub repo for the Southwestern University 2026 Capstone, Chunch Volunteer Management System Project.

This project entails a volunteer management system for the Chunch organization at the Crestview Baptist Church. These files contain a public-facing component and a private admin/captain dashboard, each with their own abilities based on someone's role. 

# Getting Started
## Dependencies
- Flask
- SQLAlchemy
- PostgreSQL
- Google Forms
- Google Sheets
- Google APIs
- Google Cloud Identity
- Render
- GitHub

## Installation and Running Program
- Fork or download the repository
- Install dependancies for Flask, SQLAlchemy, and PostgreSQL by downloading the requirements.txt file
- The website can be found at https://chunch.onrender.com
- Before being able to sign in to the admin dashboard, reach out to Bryan Scott or **TECH NAME** to be added as a tech or admin

## Files
* \_\_pycache\_\_: ??
  * app.cpython-312.pyc: ??
  * app.cpython-314.pyc: ??
* instance: __AARON__
  * chunch.db: __AARON__
  * local.db: __AARON__
  * test.db: __AARON__
* migrations: ??
  * \_\_pycache\_\_: ??
    * env.cpython-314.pyc: ??
  * versions: ??
    * 4233ac2120b0_initial_migration.cpython.pyc: ??
  * 4233ac2120b0_initial_migration.py: ??
  * alembic.ini: ??
  * env.py: ??
  * README: ??
  * script.py.mako: ??
* style: __ELEANOR__
  * application.css:
  * contribute.css: 
  * coverage.css:
  * home.css:
  * master-list.css: 
  * meet-the-team.css:
  * public.css:
  * student.css:
  * volunteer.css:
* templates:
  * absence-forms.html: __EVELYN__
  * admin.html: Dashboard for users with the admin or tech role.
  * applicant-detail.html: __EVELYN__
  * application_received.html: __EVELYN__
  * captain.html: Dashboard for users with the captain role, accessible by admin & tech roles.
  * coverage-details.html: __EVELYN__
  * deleted-volunteers.html: Table of volunteers and their information that were chosen to be deleted from the master list. Volunteers can be either permanently deleted or restored to the master list.
  * inbox.html: Inbox page on the admin dashboard that allows admins to accept or decline new volunteer applicants.
  * index.html: Public-facing component "Home" page.
  * master-list.html: Table of all current volunteers and their information. Also where new volunteers can be added or current volunteers can be deleted.
  * meet-the-team.html: Public-facing component "Meet the Team" page.
  * need-coverage.html: Page that is used by captains and admins to find coverage and submit absences for volunteers.
  * student-spotlight.html: Public-facing component "Student Spotlight" page.
  * volunteer-hours-cap.html: __ELEANOR__
  * volunteer-hours.html: Hourly view __EVELYN__
  * volunteer-intro-vids.html: Public-facing component "Volunteer" page.
* app.py: __AARON__
* credentials.json: ??
* init_db.py: __AARON__
* Procfile: __AARON__
* README.md: This document.
* requirements.txt: __AARON__

## Known Issues
The only difference between `volunteer-hours-cap.html` and `volunteer-hours.html` is that the back button routes to `/captain` instead of `/admin`. It might be redundant now that we have locked permissions. 
