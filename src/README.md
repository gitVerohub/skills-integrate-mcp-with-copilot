# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Sign up for activities

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                      | Log in as a teacher and start a session                              |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Sign up for an activity (teacher session required)                  |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student (teacher session required)                  |

Configure `TEACHER_USERNAME` and `TEACHER_PASSWORD` in the server's environment
or secret manager; there are no default credentials. Send those credentials to
`POST /auth/login` using HTTP Basic authentication. A successful login sets an
`HttpOnly`, `Secure`, `SameSite=Strict` session cookie that expires after one
hour. Signup and unregister requests must include that cookie. Invalid or
expired sessions receive `401 Unauthorized`; if credentials are not configured,
login returns `503 Service Unavailable`. Use HTTPS for login and subsequent
requests. Viewing activities remains public. Sessions are held in memory and
are invalidated when the server restarts.

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
