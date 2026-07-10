# Legacy web stack (archivé)

Ce dossier contient l'ancien stack **web Docker + NestJS**, retiré du produit Workproba (application bureau uniquement).

| Dossier / fichier | Contenu |
|---|---|
| `api/` | Backend NestJS (auth, PostgreSQL, agent-gateway) |
| `docker-compose.ai.yml` | Service Python en conteneur Docker |
| `front-docker/` | Docker Compose du front Quasar navigateur |
| `compose-all.sh` | Script de lancement Docker global |
| `bitbucket-pipelines.yml` | CI déploiement web |

**Ne pas utiliser** pour le développement produit. Voir la racine `workproba/README.md` pour le workflow bureau (Tauri + sidecar Python).
