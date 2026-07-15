# Legacy web stack (archived)

This folder contains the former **Docker + NestJS web stack**, removed from the Workproba product (desktop app only).

| Folder / file | Contents |
|---|---|
| `api/` | NestJS backend (auth, PostgreSQL, agent-gateway) |
| `docker-compose.ai.yml` | Python service in a Docker container |
| `front-docker/` | Browser Quasar front Docker Compose |
| `compose-all.sh` | Global Docker launch script |
| `bitbucket-pipelines.yml` | Web deployment CI |

**Do not use** for product development. The V3 control plane is a **new** monorepo `workproba-cloud/` (patterns réutilisables, pas ce code tel quel). See [architecture-cloud.md](../../workproba-improba/roadmaps/architecture-cloud.md). Desktop workflow: root `workproba/README.md` (Tauri + Python sidecar).
