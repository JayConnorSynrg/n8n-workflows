# AIO Voice Agent — Deploy Tooling
# Standalone repos (permanent locations for Railway deploys)
STANDALONE_DIR := $(HOME)/CODING/livekit-voice-agent
RELAY_DIR      := $(HOME)/CODING/voice-agent-relay
RELAY_SRC      := $(CURDIR)/voice-agent-poc/relay-server

.PHONY: deploy-agent sync-agent check-standalone deploy-relay sync-relay check-relay

## deploy-agent: Sync agent code to standalone repo, push to GitHub, and deploy to Railway
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
		PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "sync: from monorepo $$(git -C $(CURDIR) rev-parse --short HEAD)" || echo "Nothing to commit"
	@git -C $(STANDALONE_DIR) push origin main
	@echo "==> Deploying to Railway via railway up..."
	@cd $(STANDALONE_DIR) && railway up --detach
	@echo "==> Railway deploy triggered. Check: cd $(STANDALONE_DIR) && railway deployment list"

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

## deploy-relay: Sync relay code to standalone repo and push (triggers Railway auto-deploy)
deploy-relay: check-relay
	@echo "==> Pulling latest relay standalone..."
	@git -C $(RELAY_DIR) pull origin main
	@echo "==> Syncing relay source from monorepo..."
	@cp -r $(RELAY_SRC)/. $(RELAY_DIR)/
	@rm -rf $(RELAY_DIR)/node_modules
	@echo "==> Committing to relay standalone..."
	@cd $(RELAY_DIR) && git add -A && \
		git commit -m "sync: relay from monorepo $$(git -C $(CURDIR) rev-parse --short HEAD)" || echo "Nothing to commit"
	@git -C $(RELAY_DIR) push origin main
	@echo "==> Railway deploy triggered. Run: railway logs --service voice-agent-relay -n 30"

## sync-relay: Sync relay files only (no push)
sync-relay: check-relay
	@echo "==> Syncing relay source to standalone (no push)..."
	@cp -r $(RELAY_SRC)/. $(RELAY_DIR)/
	@rm -rf $(RELAY_DIR)/node_modules
	@echo "==> Sync complete. Review changes at $(RELAY_DIR)"

## check-relay: Verify relay standalone repo exists
check-relay:
	@if [ ! -d "$(RELAY_DIR)/.git" ]; then \
		echo "ERROR: Relay standalone repo not found at $(RELAY_DIR)"; \
		echo "Run: git clone https://github.com/JayConnorSynrg/voice-agent-relay.git $(RELAY_DIR)"; \
		exit 1; \
	fi
