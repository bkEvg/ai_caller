COMPOSE_FILE:=./docker-compose.production.yml
ARGS:=$(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))


# Docker

ps:
	docker compose -f $(COMPOSE_FILE) ps -a

up:
	docker compose -f $(COMPOSE_FILE) up $(ARGS)

stop:
	docker compose -f $(COMPOSE_FILE) stop $(ARGS)

rm: stop
	docker compose -f $(COMPOSE_FILE) rm -f $(ARGS)

build:
	docker compose -f $(COMPOSE_FILE) build $(ARGS)

create:
	docker compose -f $(COMPOSE_FILE) create $(ARGS)

start:
	docker compose -f $(COMPOSE_FILE) start $(ARGS)

restart:
	docker compose -f $(COMPOSE_FILE) restart $(ARGS)

logs:
	docker compose -f $(COMPOSE_FILE) logs -f $(ARGS)

exec:
	docker compose -f $(COMPOSE_FILE) exec -it $(ARGS)

rmi-dangling:
	docker rmi `docker images -f "dangling=true" -q`

reset: rm build create start
