# AIO Voice Agent — Deploy Tooling
# Standalone repo (permanent location for Railway deploys)
STANDALONE_DIR := $(HOME)/CODING/livekit-voice-agent

.PHONY: deploy-agent sync-agent check-standalone

## deploy-agent: Sync agent code to standalone repo and push to Railway
deploy-agent: check-standalone
	@echo "==> Pulling latest standalone..."
	@git -C $(STANDALONE_DIR) pull origin main
	@echo "==> Syncing src/ from monorepo..."
	@cp -r src/ $(STANDALONE_DIR)/src/
	@if [ -f requirements.txt ]; then cp requirements.txt $(STANDALONE_DIR)/; fi
	@if [ -f pyproject.toml ]; then cp pyproject.toml $(STANDALONE_DIR)/; fi
	@if [ -f Dockerfile ]; then cp Dockerfile $(STANDALONE_DIR)/; fi
	@echo "==> Committing to standalone..."
	@cd $(STANDALONE_DIR) && git add -A && \
		git commit -m "sync: from monorepo $$(git -C $(CURDIR) rev-parse --short HEAD)" || echo "Nothing to commit"
	@git -C $(STANDALONE_DIR) push origin main
	@echo "==> Railway deploy triggered. Run: railway logs --service livekit-voice-agent -n 30"

## sync-agent: Sync files only (no push)
sync-agent: check-standalone
	@echo "==> Syncing src/ from monorepo to standalone (no push)..."
	@cp -r src/ $(STANDALONE_DIR)/src/
	@echo "==> Sync complete. Review changes at $(STANDALONE_DIR)"

## check-standalone: Verify standalone repo exists at permanent path
check-standalone:
	@if [ ! -d "$(STANDALONE_DIR)/.git" ]; then \
		echo "ERROR: Standalone repo not found at $(STANDALONE_DIR)"; \
		echo "Run: git clone https://github.com/JayConnorSynrg/livekit-voice-agent.git $(STANDALONE_DIR)"; \
		exit 1; \
	fi
