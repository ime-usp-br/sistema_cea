# Operações locais padronizadas da stack de aplicação.
#
# O compose lê o .env da raiz automaticamente. Em CI/Portainer as variáveis
# podem vir exportadas no shell; nenhum alvo exige .env quando elas existem.
SHELL := /bin/bash

COMPOSE_PROJECT_NAME ?= sistema_cea
COMPOSE ?= docker compose -p $(COMPOSE_PROJECT_NAME)
COMPOSE_FILE ?= docker-compose.yml
APP_SERVICE ?= web
FILE ?=
RESTORE_ARGS ?=

.PHONY: help up up-local down migrate seed test test-e2e logs ps health config prod-check shell db-check backup-db restore-db

help:
	@echo "Alvos disponíveis:"
	@echo "  up            Sobe a stack única de aplicação (variáveis do ambiente atual)"
	@echo "  up-local      Sobe com hot reload local (docker-compose.local.yml)"
	@echo "  down          Derruba a stack de aplicação"
	@echo "  migrate       Roda as migrações no serviço web"
	@echo "  seed          Roda seed_demo (bloqueado em APP_ENV=prod)"
	@echo "  test          Roda pytest na stack isolada de testes"
	@echo "  test-e2e      Roda a suíte E2E de navegador (stack descartável)"
	@echo "  logs          Acompanha logs de web e worker"
	@echo "  ps            Status dos serviços"
	@echo "  health        Valida o healthcheck da aplicação"
	@echo "  config        Valida docker compose config"
	@echo "  prod-check    Valida ausência de banco/portas/bind mounts na stack"
	@echo "  shell         Abre shell no container web"
	@echo "  db-check      Valida a conexão com o banco externo por domínio"
	@echo "  backup-db     Executa scripts/backup-db.sh dentro do container"
	@echo "  restore-db    Restaura um backup (FILE=... [--confirm-prod])"

up:
	$(COMPOSE) -f $(COMPOSE_FILE) up -d --build

up-local:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.local.yml up -d --build

down:
	$(COMPOSE) -f $(COMPOSE_FILE) down

migrate:
	$(COMPOSE) -f $(COMPOSE_FILE) exec $(APP_SERVICE) python manage.py migrate

seed:
	@if [ "$${APP_ENV:-dev}" = "prod" ]; then \
		echo "seed bloqueado com APP_ENV=prod."; exit 1; \
	fi
	$(COMPOSE) -f $(COMPOSE_FILE) exec $(APP_SERVICE) python manage.py seed_demo

test:
	docker compose -p sistema_cea_test -f docker-compose.test.yml run --rm --build app python -m pytest

test-e2e:
	./scripts/run_e2e.sh

logs:
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=200 web worker

ps:
	$(COMPOSE) -f $(COMPOSE_FILE) ps

health:
	$(COMPOSE) -f $(COMPOSE_FILE) exec $(APP_SERVICE) /app/scripts/healthcheck.sh

config:
	$(COMPOSE) -f $(COMPOSE_FILE) config

prod-check:
	COMPOSE_FILE=$(COMPOSE_FILE) ./scripts/prod-check.sh

shell:
	$(COMPOSE) -f $(COMPOSE_FILE) exec $(APP_SERVICE) bash

db-check:
	$(COMPOSE) -f $(COMPOSE_FILE) run --rm $(APP_SERVICE) /app/scripts/wait-for-db.sh

backup-db:
	$(COMPOSE) -f $(COMPOSE_FILE) exec $(APP_SERVICE) /app/scripts/backup-db.sh

restore-db:
	@test -n "$(FILE)" || { echo "uso: make restore-db FILE=backups/arquivo.sql.gz [--confirm-prod]"; exit 1; }
	$(COMPOSE) -f $(COMPOSE_FILE) run --rm \
		-v "$(abspath $(FILE)):/restore/$(notdir $(FILE)):ro" \
		$(APP_SERVICE) /app/scripts/restore-db.sh "/restore/$(notdir $(FILE))" $(RESTORE_ARGS)
