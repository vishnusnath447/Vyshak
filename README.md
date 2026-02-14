<!-- /app
  /api
    v1/
      endpoints.py
  /core
    config.py
    security.py
  /models
    user.py
  /schemas
    user.py
  /services
    auth.py
    mailer.py
  /db
    session.py
  main.py
tests/
alembic/
Dockerfile
docker-compose.yml
.github/workflows/ci.yml -->
## Quick start (local)

- Build & run locally with Docker Compose:

  docker compose up --build

- Open http://localhost:8000/docs for the API docs.
- Chat UI: http://localhost:8000/api/v1/chat

## Deploy with GitHub Actions → Fly.io

1. Create a Fly account and install `flyctl` locally.
2. Create a Fly app: `flyctl apps create your-app-name` (or `flyctl launch`).
3. Add two repository secrets in GitHub: `FLY_API_TOKEN` and `FLY_APP` (the app name).
4. Push to `main` — the `deploy` workflow will run and deploy the container.
