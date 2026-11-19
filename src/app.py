"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import hashlib
import os
from pathlib import Path
import secrets
from typing import Optional
from time import time as current_time

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")
teacher_auth = HTTPBasic(auto_error=False)
TEACHER_SESSION_COOKIE = "teacher_session"
TEACHER_SESSION_LIFETIME_SECONDS = 3600
teacher_sessions = {}

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


def authenticate_teacher(
    credentials: Optional[HTTPBasicCredentials],
) -> None:
    """Validate teacher credentials configured outside the repository."""
    username = os.environ.get("TEACHER_USERNAME")
    password = os.environ.get("TEACHER_PASSWORD")
    if not username or not password:
        raise HTTPException(
            status_code=503,
            detail="Teacher authentication is not configured",
        )

    provided_username = credentials.username if credentials else ""
    provided_password = credentials.password if credentials else ""
    username_matches = secrets.compare_digest(
        provided_username.encode("utf-8"), username.encode("utf-8")
    )
    password_matches = secrets.compare_digest(
        provided_password.encode("utf-8"), password.encode("utf-8")
    )
    if not username_matches or not password_matches:
        raise HTTPException(
            status_code=401,
            detail="Invalid teacher credentials",
            headers={"WWW-Authenticate": 'Basic realm="teacher"'},
        )


@app.post("/auth/login")
def login(
    response: Response,
    credentials: Optional[HTTPBasicCredentials] = Depends(teacher_auth),
):
    authenticate_teacher(credentials)

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    now = current_time()
    for existing_token, expires_at in list(teacher_sessions.items()):
        if expires_at <= now:
            del teacher_sessions[existing_token]
    teacher_sessions[token_hash] = now + TEACHER_SESSION_LIFETIME_SECONDS

    response.set_cookie(
        key=TEACHER_SESSION_COOKIE,
        value=token,
        max_age=TEACHER_SESSION_LIFETIME_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {
        "message": "Teacher login successful",
        "expires_in": TEACHER_SESSION_LIFETIME_SECONDS,
    }


def require_teacher(
    session_token: Optional[str] = Cookie(
        default=None,
        alias=TEACHER_SESSION_COOKIE,
    ),
) -> None:
    """Require a valid, unexpired teacher session."""
    token_hash = (
        hashlib.sha256(session_token.encode("ascii")).hexdigest()
        if session_token
        else None
    )
    expires_at = teacher_sessions.get(token_hash) if token_hash else None
    if expires_at is None or expires_at <= current_time():
        if token_hash:
            teacher_sessions.pop(token_hash, None)
        raise HTTPException(
            status_code=401,
            detail="Teacher authentication required or expired",
        )


@app.post(
    "/activities/{activity_name}/signup",
    dependencies=[Depends(require_teacher)],
)
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete(
    "/activities/{activity_name}/unregister",
    dependencies=[Depends(require_teacher)],
)
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
