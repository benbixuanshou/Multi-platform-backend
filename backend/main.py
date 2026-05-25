"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import auth, comments, drafts, batch, posts, settings, analytics, internal, agents


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB pool, Redis, Milvus
    yield
    # Shutdown: close connections


app = FastAPI(title="Multi-platform Comment Management", lifespan=lifespan)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(comments.router, prefix="/api/comments", tags=["comments"])
app.include_router(drafts.router, prefix="/api", tags=["drafts"])
app.include_router(batch.router, prefix="/api/batch", tags=["batch"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(internal.router, prefix="/api/internal", tags=["internal"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
