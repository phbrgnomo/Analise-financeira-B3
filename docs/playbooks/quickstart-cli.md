# Quickstart CLI

Este documento descreve os passos mínimos para instalar o projeto e usar a CLI, incluindo a saída em JSON (`--format json`) e exemplos práticos.

Pré-requisitos
- Python 3.12 (virtualenv/poetry recomendado)
- `poetry` instalado (opcional) ou use `pip` conforme `pyproject.toml`

Instalação

1. Clonar o repositório

```bash
git clone https://github.com/phbrgnomo/Analise-financeira-B3.git
cd Analise-financeira-B3
```

2. Instalar dependências (modo dev):

```bash
poetry install
# ou, sem poetry:
# python -m venv .venv
# source .venv/bin/activate
# pip install -r requirements-dev.txt
```

Uso básico

Executar ingest e gerar snapshot (exemplo):

```bash
poetry run main --ticker PETR4.SA --force-refresh
```

Saída JSON (`--format json`)

Alguns comandos aceitam `--format json` para saída estruturada (útil para CI e scripts automáticos):

```bash
poetry run main --ticker PETR4.SA --start 2020-01-01 --format json
```

A saída JSON inclui campos de metadados quando aplicável: `ticker`, `snapshot_path`, `rows`, `checksum`, `snapshot_date`, `schema_version`.

Exemplos rápidos

- Forçar refresh e escrever metadados:

```bash
poetry run main --ticker PETR4.SA --force-refresh --format json > out.json
jq . out.json
```

- Validar metadados gerados (usar o script de validação incluído):

```bash
python3 scripts/validate_metadata.py out.json
```

Verificação de snapshots

- Verifique localmente:

```bash
ls -l snapshots/
sha256sum snapshots/PETR4_snapshot.csv
```

Notas

- Alinhe a versão do Python com `pyproject.toml` antes de executar (`python = "^3.12"`).
- Se a CLI mudar flags/semântica, atualize este quickstart e o README.

Checklist mínimo após seguir o quickstart

- [ ] Snapshot criado em `snapshots/`
- [ ] Checksum SHA256 disponível e registrado
- [ ] Metadados gerados e validados com `scripts/validate_metadata.py`

Referências
- Contrato de metadados: `docs/schema.md`
- Playbook: `docs/playbooks/quickstart-ticker.md` (fluxo completo)
