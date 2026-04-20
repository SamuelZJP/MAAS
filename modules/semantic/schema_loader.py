from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# TODO: 添加自定义错误类，用于捕获语义记忆快照构建、验证、转换等操作失败的情况
class SemanticSchemaError(Exception):
    pass


# 构建默认语义记忆快照：根据 Schema 模型构建默认语义记忆快照
def build_default_snapshot(chat_id: str) -> dict[str, Any]:
    schema_model = load_schema_model(chat_id)
    instance = schema_model()
    return _dump_model(instance)


# 验证语义记忆快照：验证语义记忆快照是否符合 Schema 模型
def validate_snapshot(chat_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    schema_model = load_schema_model(chat_id)
    instance = schema_model.model_validate(snapshot)
    return _dump_model(instance)


# 将语义记忆快照转换为 YAML 格式：将语义记忆快照转换为 YAML 格式
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


# 加载参考信息：加载参考信息
def load_reference_info(chat_id: str) -> str:
    return _load_required_text_export(chat_id, "REFERENCE_INFO")


# 加载变量更新规则：加载变量更新规则
def load_variable_update_rules(chat_id: str) -> str:
    return _load_required_text_export(chat_id, "VARIABLE_UPDATE_RULES")


# 加载 Schema 模型：加载 Schema 模型
def load_schema_model(chat_id: str) -> type[BaseModel]:
    file_path = DATA_DIR / f"{chat_id}.py"
    if not file_path.exists():
        raise SemanticSchemaError(f"Semantic schema file not found for chat '{chat_id}'.")

    module = _load_module(file_path, chat_id)
    schema_model = getattr(module, "Schema", None)
    if not isinstance(schema_model, type) or not issubclass(schema_model, BaseModel):
        raise SemanticSchemaError(f"Schema class is missing or invalid in '{file_path.name}'.")
    return schema_model


# 加载模块：加载模块
def _load_module(file_path: Path, chat_id: str) -> ModuleType:
    module_name = f"maas_semantic_schema_{chat_id}"
    spec = spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise SemanticSchemaError(f"Unable to load schema spec from '{file_path.name}'.")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# 加载必需的文本导出：加载必需的文本导出
def _load_required_text_export(chat_id: str, export_name: str) -> str:
    file_path = DATA_DIR / f"{chat_id}.py"
    if not file_path.exists():
        raise SemanticSchemaError(f"Semantic schema file not found for chat '{chat_id}'.")

    module = _load_module(file_path, chat_id)
    value = getattr(module, export_name, None)
    if not isinstance(value, str) or not value.strip():
        raise SemanticSchemaError(f"{export_name} is missing or invalid in '{file_path.name}'.")
    return value.strip()


# 将模型实例转换为字典：将模型实例转换为字典
def _dump_model(instance: BaseModel) -> dict[str, Any]:
    return instance.model_dump(mode="json")
