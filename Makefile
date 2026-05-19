# SiSEsperanza — operaciones Docker Swarm / GHCR
# Uso: make deploy   (requiere .env en el VPS con las variables del stack)

IMAGE       ?= ghcr.io/byronmoreno/siseesperanza
STACK       ?= sise
VERSION     ?= latest
GHCR_USER   ?= byronmoreno
COMPOSE_FILE = stack.yml

.PHONY: build push deploy logs restart rollback remove status pull

build:
	docker build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .

push: build
	docker push $(IMAGE):$(VERSION)
	docker push $(IMAGE):latest

pull:
	docker pull $(IMAGE):$(VERSION)

deploy:
	set -a && . ./.env && set +a && \
	docker stack deploy --with-registry-auth -c $(COMPOSE_FILE) $(STACK)

logs:
	docker service logs -f $(STACK)_app

logs-db:
	docker service logs -f $(STACK)_postgres

restart:
	docker service update --force $(STACK)_app

rollback:
	docker service rollback $(STACK)_app

remove:
	docker stack rm $(STACK)

status:
	docker stack ps $(STACK)
	docker service ls --filter label=com.docker.stack.namespace=$(STACK)
