.PHONY: install test demo api hooks scan licenses notebooks lint calibrate kind-up kind-down dashboard

install:
	pip install -e ".[dev,notebooks]"

lint:
	ruff check src tests
	ruff format --check src tests

test:
	pytest

demo:
	FC_LLM_PROVIDER=fake FC_DATABASE_URL=sqlite:///./data/demo.db \
		FC_CALIBRATOR_PATH=./models/demo_calibrator.json \
		FC_TRACK_RECORD_DIR=./public_demo \
		forecaster demo --questions 100

api:
	FC_ENABLE_DOCS=false uvicorn forecaster.api:app --host 127.0.0.1 --port 8000

hooks:
	pre-commit install

scan:
	gitleaks detect --source . --no-git -v --config .gitleaks.toml

licenses:
	pip-licenses --format=markdown --with-urls --fail-on="GPL;AGPL" > licenses-report.md

notebooks:
	jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb

calibrate:
	forecaster calibrate

dashboard:
	forecaster dashboard

kind-up:
	kind create cluster --name forecaster --config deploy/kind/cluster.yaml
	kubectl apply -f deploy/namespace.yaml
	kubectl apply -f deploy/kind/postgres.yaml
	kubectl -n forecaster rollout status deployment/postgres --timeout=60s
	docker build -t llm-forecast-pipeline:local .
	kind load docker-image llm-forecast-pipeline:local --name forecaster
	helm upgrade --install forecaster deploy/helm/forecaster --namespace forecaster
	kubectl -n forecaster rollout status deployment/forecaster-api --timeout=60s

kind-down:
	kind delete cluster --name forecaster
