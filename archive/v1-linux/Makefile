SHELL := /bin/bash
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install run stop status logs clean docker-build docker-run help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Full installation (venv + models + systemd)
	@chmod +x install.sh dictator.sh
	@./install.sh

venv: ## Create venv and install dependencies only
	@python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip -q
	@$(PIP) install -r requirements.txt
	@echo "Virtual environment ready."

run: ## Run manually (stops service first)
	@systemctl --user stop dictator 2>/dev/null || true
	@$(PYTHON) -u dictate.py

run-device: ## Run with device selection (usage: make run-device DEVICE="name")
	@systemctl --user stop dictator 2>/dev/null || true
	@$(PYTHON) -u dictate.py --device "$(DEVICE)"

stop: ## Stop the systemd service
	@systemctl --user stop dictator

status: ## Show service status
	@systemctl --user status dictator

logs: ## Follow service logs
	@journalctl --user -u dictator -f

devices: ## List available audio input devices
	@$(PYTHON) src/list_devices.py

clean: ## Remove venv and cached files
	@rm -rf $(VENV) __pycache__ src/__pycache__
	@echo "Cleaned."

uninstall: ## Stop, disable service, and clean
	@systemctl --user stop dictator 2>/dev/null || true
	@systemctl --user disable dictator 2>/dev/null || true
	@rm -f ~/.config/systemd/user/dictator.service
	@systemctl --user daemon-reload
	@rm -rf $(VENV) __pycache__ src/__pycache__
	@echo "Uninstalled."

docker-build: ## Build Docker image
	@docker build -t dictator .

docker-run: ## Run in Docker (requires --privileged for audio/X11)
	@docker run --rm -it \
		--privileged \
		--net=host \
		-e DISPLAY=$(DISPLAY) \
		-e PULSE_SERVER=unix:/run/user/$$(id -u)/pulse/native \
		-v /tmp/.X11-unix:/tmp/.X11-unix \
		-v $(XAUTHORITY):/root/.Xauthority:ro \
		-v /run/user/$$(id -u)/pulse:/run/user/$$(id -u)/pulse:ro \
		--device /dev/snd \
		dictator $(ARGS)
