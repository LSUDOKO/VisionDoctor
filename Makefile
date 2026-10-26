# VisionDoctor — see README.md. All targets run locally without AWS (VD_BACKEND=local).
PY ?= .venv/bin/python
UV ?= uv

.PHONY: setup lock data models test test-fast lint demo demo-sim serve mcp bench eval eval-impact calibrate figs web web-test synth deploy down clean

setup:            ## create venv and install pinned deps
	$(UV) venv -p 3.12 .venv
	$(UV) pip sync --python $(PY) requirements.lock
	$(UV) pip install --python $(PY) --no-deps -e .

lock:             ## regenerate requirements.lock from pyproject (with hashes)
	$(UV) pip compile pyproject.toml --extra opencv --extra dev --generate-hashes -o requirements.lock

data:             ## download evaluation footage (MOT17 videos + labels, vtest)
	bash scripts/download_data.sh

models:           ## download ONNX models (YOLOX, YuNet)
	bash scripts/download_models.sh

test:             ## full test suite
	$(PY) -m pytest -q

test-fast:
	$(PY) -m pytest -q tests/health tests/repair tests/impact

lint:
	$(PY) -m ruff check src tests eval bench
	$(PY) -m mypy src/visiondoctor --ignore-missing-imports || true

demo-sim:         ## 12 cameras for 60 s with the demo scenario; frames + truth in results/sim/
	$(PY) -m visiondoctor.cli sim --cameras 12 --duration 60

serve demo:       ## API + monitor + dashboard (web/dist) on http://localhost:8000
	$(PY) -m visiondoctor.cli serve --port 8000

mcp:              ## MCP server over stdio (for Claude Code / Claude Desktop)
	$(PY) -m visiondoctor.mcp_server.server --transport stdio

calibrate:        ## clean-footage threshold calibration → results/calibration/
	$(PY) eval/calibrate.py

eval-impact:      ## build dataset, train + validate impact predictor (E3)
	$(PY) eval/make_impact_dataset.py
	$(PY) eval/e3_impact.py

eval:             ## E1–E5 evaluation → results/
	$(PY) eval/e1_detection.py
	$(PY) eval/e2_false_alarms.py
	$(PY) eval/e3_impact.py
	$(PY) eval/e4_repair.py
	$(PY) eval/e5_agent.py
	$(PY) eval/summarize.py

bench:            ## OpenCV micro + end-to-end benchmark for this host → results/bench/<host>/
	$(PY) bench/run.py

figs:
	$(PY) scripts/make_report_figs.py

web:
	cd web && npm ci && npm run build

web-test:
	cd web && npx playwright test

synth:            ## CDK synth (+ cdk-nag)
	cd infra && npx -y aws-cdk@2.1146.1 synth -c coolAmiId=$${COOL_AMI_ID:-ami-00000000000000000}

deploy:           ## real AWS deploy (costs money; needs COOL Marketplace subscription)
	cd infra && npx -y aws-cdk@2.1146.1 deploy --all -c coolAmiId=$${COOL_AMI_ID:?set COOL_AMI_ID}

down:             ## destroy all stacks; also cancel the COOL Marketplace trial!
	cd infra && npx -y aws-cdk@2.1146.1 destroy --all
	@echo "Remember to cancel the COOL Marketplace subscription."

clean:
	rm -rf vd_state results/sim .pytest_cache
