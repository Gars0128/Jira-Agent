from fastapi import FastAPI

app = FastAPI(title="Discovery to Jira Agent")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
