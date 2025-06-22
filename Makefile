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

prune:
	docker compose -f $(COMPOSE_FILE) image prune -f

rmi-dangling:
	docker rmi `docker images -f "dangling=true" -q`

clean-volumes:
	docker volume prune -f

clean-system:
	docker system prune -f

clean-all:
	@echo ""
	@echo "ВНИМАНИЕ! Это удалит:"
	@echo "  - неиспользуемые образы (в том числе висячие)"
	@echo "  - volume'ы без контейнеров"
	@echo "  - dangling образы"
	@echo "  - build cache и сети"
	@echo ""
	@read -p 'Продолжить? [y/N]: ' confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		$(MAKE) rmi-dangling; \
		$(MAKE) prune; \
		$(MAKE) clean-volumes; \
		$(MAKE) clean-system; \
		echo "Очистка завершена."; \
	else \
		echo "Отменено."; \
	fi

reset: rm build create start
