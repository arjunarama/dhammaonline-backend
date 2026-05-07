from dotenv import load_dotenv

load_dotenv()

import os

from fastapi.security import OAuth2PasswordBearer
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    UploadFile,
    File,
)

import cloudinary.uploader
import cloudinary_config
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from auth import (
    create_access_token,
    hash_password,
    verify_token,
    verify_password,
)
from database import engine, create_db_and_tables
from models import Teaching, Admin

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="login"
)

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateAdminRequest(BaseModel):
    username: str
    password: str
    role: str


origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://dhammaonline.vercel.app",
    "https://dhammaonline-admin.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def home():
    return {
        "message": "Dhamma Online FastAPI Backend Running"
    }


@app.get("/teachings")
def get_teachings():
    with Session(engine) as session:
        teachings = session.exec(
            select(Teaching)
        ).all()

        return teachings


@app.get("/teachings/{slug}")
def get_teaching_by_slug(slug: str):
    with Session(engine) as session:
        teaching = session.exec(
            select(Teaching).where(Teaching.slug == slug)
        ).first()

        if not teaching:
            raise HTTPException(
                status_code=404,
                detail="Teaching not found"
            )

        return teaching


@app.post("/teachings")
def create_teaching(
    teaching: Teaching,
    token: str = Depends(oauth2_scheme),
):

    verify_token(token)

    with Session(engine) as session:
        session.add(teaching)
        session.commit()
        session.refresh(teaching)

        return teaching


@app.put("/teachings/{teaching_id}")
def update_teaching(
    teaching_id: int,
    updated_teaching: Teaching
):
    with Session(engine) as session:

        teaching = session.get(
            Teaching,
            teaching_id
        )

        if not teaching:
            return {
                "error": "Teaching not found"
            }

        teaching.title = updated_teaching.title
        teaching.category = updated_teaching.category

        session.add(teaching)
        session.commit()
        session.refresh(teaching)

        return teaching


@app.delete("/teachings/{teaching_id}")
def delete_teaching(teaching_id: int):
    with Session(engine) as session:

        teaching = session.get(
            Teaching,
            teaching_id
        )

        if not teaching:
            return {
                "error": "Teaching not found"
            }

        session.delete(teaching)
        session.commit()

        return {
            "message": "Teaching deleted successfully"
        }


@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    superadmin_username = os.getenv(
        "SUPERADMIN_USERNAME"
    )

    superadmin_password = os.getenv(
        "SUPERADMIN_PASSWORD"
    )

    # SUPERADMIN LOGIN
    if (
        form_data.username == superadmin_username
        and
        form_data.password == superadmin_password
    ):

        token = create_access_token({
            "sub": form_data.username,
            "role": "superadmin",
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "role": "superadmin",
        }

    # DATABASE ADMIN LOGIN
    with Session(engine) as session:

        admin = session.exec(
            select(Admin).where(
                Admin.username == form_data.username
            )
        ).first()

        if not admin:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        valid_password = verify_password(
            form_data.password,
            admin.password,
        )

        if not valid_password:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        token = create_access_token({
            "sub": admin.username,
            "role": admin.role,
        })

        return {
            "access_token": token,
            "token_type": "bearer",
            "role": admin.role,
        }

@app.post("/create-admin")
def create_admin(
    data: CreateAdminRequest,
    token: str = Depends(oauth2_scheme),
):

    payload = verify_token(token)

    if payload["role"] != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )
    
    if data.username == os.getenv("SUPERADMIN_USERNAME"):
        raise HTTPException(
            status_code=400,
            detail="Username already reserved"
        )

    with Session(engine) as session:

        existing_admin = session.exec(
            select(Admin).where(
                Admin.username == data.username
            )
        ).first()

        if existing_admin:
            raise HTTPException(
                status_code=400,
                detail="Username already exists"
            )

        admin = Admin(
            username=data.username,
            password=hash_password(data.password),
            role=data.role,
        )

        session.add(admin)

        session.commit()

        session.refresh(admin)

        return {
            "message": "Admin created successfully"
        }
    
@app.get("/admins")
def get_admins(
    token: str = Depends(oauth2_scheme),
):
    payload = verify_token(token)

    if payload["role"] != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    with Session(engine) as session:

        admins = session.exec(
            select(Admin)
        ).all()

        return admins
    
@app.put("/admins/{admin_id}")
def update_admin(
    admin_id: int,
    data: CreateAdminRequest,
    token: str = Depends(oauth2_scheme),
):
    payload = verify_token(token)

    if payload["role"] != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    with Session(engine) as session:

        admin = session.get(
            Admin,
            admin_id
        )

        if not admin:
            raise HTTPException(
                status_code=404,
                detail="Admin not found"
            )

        admin.username = data.username
        admin.password = hash_password(
            data.password
        )
        admin.role = data.role

        session.add(admin)

        session.commit()

        session.refresh(admin)

        return admin
    
@app.delete("/admins/{admin_id}")
def delete_admin(
    admin_id: int,
    token: str = Depends(oauth2_scheme),
):

    payload = verify_token(token)

    if payload["role"] != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    with Session(engine) as session:

        admin = session.get(
            Admin,
            admin_id
        )

        if not admin:
            raise HTTPException(
                status_code=404,
                detail="Admin not found"
            )

        session.delete(admin)

        session.commit()

        return {
            "message": "Admin deleted successfully"
        }
    
@app.post("/upload-image")
def upload_image(
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
):

    verify_token(token)

    try:

        result = cloudinary.uploader.upload(
            file.file
        )

        return {
            "image_url": result["secure_url"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Image upload failed: {e}"
        )
