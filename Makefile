COMPOSE_FILE:=./docker-compose.production.yml
ARGS:=$(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))


help:
	@echo "Доступные команды:"
	@echo ""
	@echo "  make up [service]        	 Запуск контейнеров (или конкретного сервиса)"
	@echo "  make stop [service]      	 Остановка контейнеров"
	@echo "  make rm [service]        	 Остановка и удаление контейнеров"
	@echo "  make build [service]     	 Сборка контейнеров"
	@echo "  make create [service]    	 Создание контейнеров без запуска"
	@echo "  make start [service]     	 Запуск уже созданных контейнеров"
	@echo "  make restart [service]   	 Перезапуск контейнеров"
	@echo "  make logs [service]      	 Логи контейнеров в реальном времени"
	@echo "  make exec [service] shell	 Войти в контейнер (пример: exec web bash)"
	@echo "  make ps                  	 Посмотреть список контейнеров"
	@echo "  make rmi-dangling        	 Удалить висячие образы (без тегов)"
	@echo "  make clean-all         	 Провести полную уборку"
	@echo "  make reset               	 Полный ресет: rm → build → create → start"
	@echo ""
	@echo "Примеры:"
	@echo "  make up web        — Запустить только сервис web"
	@echo "  make exec web bash — Войти в bash внутри web"

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

prune:
	docker image prune -f

clean-volumes:
	docker volume prune -f

clean-system:
	docker system prune -f

clean-all:
	@if [ "$(CONFIRM)" != "false" ]; then \
		echo ""; \
		echo "ВНИМАНИЕ! Это удалит:"; \
		echo "  - неиспользуемые образы (в том числе висячие)"; \
		echo "  - volume'ы без контейнеров"; \
		echo "  - dangling образы"; \
		echo "  - build cache и сети"; \
		echo ""; \
		read -p 'Продолжить? [y/N]: ' confirm; \
		if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
			echo "Отменено пользователем."; \
			exit 0; \
		fi \
	fi; \
	$(MAKE) rmi-dangling; \
	$(MAKE) prune; \
	$(MAKE) clean-volumes; \
	$(MAKE) clean-system; \
	echo "Очистка завершена."

reset: rm build create start
