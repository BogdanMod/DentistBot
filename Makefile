.PHONY: build up down logs restart shell

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f bot

restart:
	docker-compose restart bot

shell:
	docker-compose exec bot bash