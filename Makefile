start:
	docker compose up --build -d

up:
	docker compose up -d

down:
	docker compose down

clean:
	docker compose down -v
