PY?=python3
CLI=./ops/admin_cli.py

# Set BASE_URL, DOORMAN_ADMIN_EMAIL, DOORMAN_ADMIN_PASSWORD via env or defaults

.PHONY: metrics dump restore chaos-on chaos-off chaos-stats revoke enable-user disable-user rotate-admin

metrics:
	$(PY) $(CLI) --yes metrics

dump:
	$(PY) $(CLI) dump --yes $(if $(PATH),--path $(PATH),)

restore:
	$(PY) $(CLI) restore --yes $(if $(PATH),--path $(PATH),)

chaos-on:
	$(PY) $(CLI) chaos redis --enabled --duration-ms $(or $(DURATION),15000) --yes

chaos-off:
	$(PY) $(CLI) chaos redis --duration-ms 0 --yes || true

chaos-stats:
	$(PY) $(CLI) chaos-stats

revoke:
	$(PY) $(CLI) revoke $(USER) --yes

enable-user:
	$(PY) $(CLI) enable-user $(USER) --yes

disable-user:
	$(PY) $(CLI) disable-user $(USER) --yes

rotate-admin:
	$(PY) $(CLI) rotate-admin --yes $(if $(PASSWORD),--password $(PASSWORD),)

