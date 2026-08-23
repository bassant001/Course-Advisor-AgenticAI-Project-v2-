from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from api.routes import router, limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from src.observability.obs import setup_logging



app = FastAPI(
    title="Course Advisor API",
    version="1.0.0",
    description="Backend API for the Course Advisor agentic system.",
)

app.include_router(router)


# benrabet el limiter bel fastapi app
app.state.limiter = limiter

# 3ashan law el client 3amal requests aktar men el limit
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)


# 3ashan nsagel kol request fe struc json
logger = setup_logging()


@app.get("/service")
async def service():
    return {
        "status": "ok",
        "service": "course-advisor-api",
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "unhandled_exception",
        extra={
            "path": request.url.path,
            "method": request.method,
        },
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error."
        },
    )