.PHONY: help dev dev-all dev-ai dev-front dev-desktop

AI_DIR = services/ai
FRONT_DIR = front
DESKTOP_DIR = desktop

help:
	@echo ''
	@echo 'Workproba — application bureau'
	@echo ''
	@echo '  dev             - Tout en un : sidecar Python + desktop Tauri (Ctrl+C arrête les deux)'
	@echo '  dev-all         - Alias de dev'
	@echo '  dev-ai          - Sidecar Python seul (port 8765)'
	@echo '  dev-front       - Quasar dev server seul (port 5053)'
	@echo '  dev-desktop     - Tauri + Quasar (sidecar à lancer à part)'
	@echo ''

dev dev-all:
	bash scripts/dev-all.sh

dev-ai:
	cd $(AI_DIR) && ./run_dev.sh

dev-front:
	cd $(FRONT_DIR) && yarn dev

dev-desktop:
	cd $(DESKTOP_DIR) && yarn dev
