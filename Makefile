.PHONY: help dev dev-ai dev-front dev-desktop

AI_DIR = services/ai
FRONT_DIR = front
DESKTOP_DIR = desktop

help:
	@echo ''
	@echo 'Workproba — application bureau'
	@echo ''
	@echo '  dev             - Instructions de développement'
	@echo '  dev-ai          - Sidecar Python (port 8765)'
	@echo '  dev-front       - Quasar dev server (port 5053)'
	@echo '  dev-desktop     - Tauri + Quasar'
	@echo ''

dev:
	@echo ''
	@echo 'Workflow typique :'
	@echo '  Terminal 1:  make dev-ai'
	@echo '  Terminal 2:  make dev-desktop'
	@echo ''
	@echo 'Ou : bash scripts/dev.sh  puis  cd desktop && yarn dev'

dev-ai:
	cd $(AI_DIR) && ./run_dev.sh

dev-front:
	cd $(FRONT_DIR) && yarn dev

dev-desktop:
	cd $(DESKTOP_DIR) && yarn dev
