import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.routers import auth, payments

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="API",
    description="FastAPI with auth and payment support",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with actual origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])

@app.get("/")
async def root():
    return {"message": "Welcome to the API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}