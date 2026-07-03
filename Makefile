COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

start:
	$(COMPOSE) up --build

up:
	$(COMPOSE) up

download-data:
	$(COMPOSE) run --rm --build app python src/download_kaggle.py

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v

clean-data:
	$(COMPOSE) down -v
	sudo rm -fr data/raw

clean-cache:
	sudo rm -fr data/cache/
	sudo rm -fr data/key/
	sudo rm -fr data/db_dumps/

prune-all:
	$(COMPOSE) down -v --rmi all --remove-orphans
	docker system prune -a --volumes -f

prune:
	docker system prune -a --volumes -f