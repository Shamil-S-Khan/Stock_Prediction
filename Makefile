.PHONY: help build up down restart logs clean test

help:
    @echo "Finance Forecasting Docker Commands:"
    @echo "  make build    - Build Docker images"
    @echo "  make up       - Start all services"
    @echo "  make down     - Stop all services"
    @echo "  make restart  - Restart all services"
    @echo "  make logs     - View logs"
    @echo "  make clean    - Remove containers and volumes"
    @echo "  make test     - Run tests inside container"

build:
    docker-compose build

up:
    docker-compose up -d
    @echo "Application running at http://localhost:5000"
    @echo "MongoDB running at mongodb://localhost:27017"

down:
    docker-compose down

restart:
    docker-compose restart

logs:
    docker-compose logs -f app

logs-db:
    docker-compose logs -f mongodb

clean:
    docker-compose down -v
    docker system prune -f

test:
    docker-compose exec app pytest test/

shell:
    docker-compose exec app /bin/bash

db-shell:
    docker-compose exec mongodb mongosh -u admin -p password123