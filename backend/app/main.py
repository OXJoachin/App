from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .auth import create_access_token, get_current_user
from .crud import create_cycle, get_dashboard_data, get_user_cycles, register_user, authenticate_user
from .database import Base, engine, get_db
from .models import User
from .schemas import CycleCreate, CycleOut, UserCreate, UserLogin, UserOut

app = FastAPI(title="Suivi des règles", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.post("/api/register", response_model=UserOut)
def api_register(user_data: UserCreate, db: Session = Depends(get_db)) -> User:
    try:
        new_user = register_user(db, user_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return new_user


@app.post("/api/login")
def api_login(user_data: UserLogin, db: Session = Depends(get_db)) -> dict[str, Any]:
    user = authenticate_user(db, user_data.identifier, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur/email ou mot de passe incorrect.",
        )

    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
    }


@app.get("/api/me", response_model=UserOut)
def api_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.post("/api/cycles", response_model=CycleOut)
def api_create_cycle(
    cycle_data: CycleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CycleOut:
    try:
        cycle = create_cycle(db, current_user.id, cycle_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return cycle


@app.get("/api/cycles", response_model=list[CycleOut])
def api_list_cycles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_cycles(db, current_user.id)


@app.get("/api/dashboard")
def api_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_dashboard_data(db, current_user.id)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "API de suivi des règles active."}
