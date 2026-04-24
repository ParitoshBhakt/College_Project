from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.routes.emotion import router as emotion_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.middleware.error_handler import register_error_handlers
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.user import User


setup_logging()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
register_error_handlers(app)
app.include_router(emotion_router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        demo_user = db.execute(select(User).where(User.id == 1)).scalar_one_or_none()
        if demo_user is None:
            db.add(
                User(
                    id=1,
                    email="demo@sentiface.ai",
                    full_name="SentiFace Demo",
                    hashed_password=hash_password("Demo@12345"),
                )
            )
            db.commit()
    finally:
        db.close()