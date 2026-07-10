import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import db_connection
from app.routers import auth, users, kpis, orders, products, partners, chatbot, supplier
from app.services.anomaly_sync import sync_anomalies_to_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # fire up the MongoDB database connection, dude
    await db_connection.connect_to_database()
    # background task to sync KNN anomaly statuses in MongoDB
    asyncio.create_task(sync_anomalies_to_db(db_connection.db))
    yield
    # clean shutdown: disconnect from MongoDB
    await db_connection.close_database_connection()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="FastAPI Backend for Smart Supply Chain Dashboard (with JWT & MongoDB)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# permit CORS requests so local Angular dev server can talk to backend
origins = [
    "http://localhost",
    "http://localhost:4200",
    "http://127.0.0.1",
    "http://127.0.0.1:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],

)

# mount all API routing groups under the /api prefix
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(kpis.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(partners.router, prefix="/api")
app.include_router(chatbot.router, prefix="/api")
app.include_router(supplier.router, prefix="/api")


@app.get("/", tags=["Health Check"])
def read_root():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "docs": "/docs"
    }
