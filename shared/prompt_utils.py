# 提示词模板渲染工具（基于 Jinja2）

from jinja2 import Environment, StrictUndefined


_environment = Environment(
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


# 渲染 Jinja2 模板字符串，返回去首尾空白的结果
def render_prompt(template_str: str, **kwargs: object) -> str:
    template = _environment.from_string(template_str)
    return template.render(**kwargs).strip()
