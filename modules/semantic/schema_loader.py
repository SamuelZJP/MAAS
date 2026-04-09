from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class SemanticSchemaError(Exception):
    pass


def build_default_snapshot(chat_id: str) -> dict[str, Any]:
    schema_model = load_schema_model(chat_id)
    instance = schema_model()
    return _dump_model(instance)


def validate_snapshot(chat_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    schema_model = load_schema_model(chat_id)
    instance = schema_model.model_validate(snapshot)
    return _dump_model(instance)


def dump_snapshot_yaml(chat_id: str, snapshot: dict[str, Any]) -> str:
    try:
        import yaml
    except ImportError as exc:
        raise SemanticSchemaError("PyYAML is required for semantic memory YAML rendering.") from exc

    validated_snapshot = validate_snapshot(chat_id, snapshot)
    return yaml.safe_dump(
        validated_snapshot,
        allow_unicode=True,
        sort_keys=False,
    ).strip()


def load_schema_model(chat_id: str) -> type[BaseModel]:
    file_path = DATA_DIR / f"{chat_id}.py"
    if not file_path.exists():
        raise SemanticSchemaError(f"Semantic schema file not found for chat '{chat_id}'.")

    module = _load_module(file_path, chat_id)
    schema_model = getattr(module, "Schema", None)
    if not isinstance(schema_model, type) or not issubclass(schema_model, BaseModel):
        raise SemanticSchemaError(f"Schema class is missing or invalid in '{file_path.name}'.")
    return schema_model


def _load_module(file_path: Path, chat_id: str) -> ModuleType:
    module_name = f"maas_semantic_schema_{chat_id}"
    spec = spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise SemanticSchemaError(f"Unable to load schema spec from '{file_path.name}'.")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dump_model(instance: BaseModel) -> dict[str, Any]:
    return instance.model_dump(mode="json")
