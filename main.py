import uvicorn
from fastapi import FastAPI
from routers import webhook, agent, memory, overrides, messages, ops

app = FastAPI(title="Visa Sales Agent API", version="1.0.0")

# Routers
app.include_router(webhook.router)
app.include_router(agent.router,    prefix="/v1/agent",    tags=["agent"])
app.include_router(memory.router,   prefix="/v1/memory",   tags=["memory"])
app.include_router(overrides.router,prefix="/v1/overrides",tags=["overrides"])
app.include_router(messages.router, prefix="/v1/messages", tags=["messages"])
app.include_router(ops.router,                          tags=["ops"])

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", "3000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
