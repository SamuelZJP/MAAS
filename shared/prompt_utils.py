from jinja2 import Environment, StrictUndefined


_environment = Environment(
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


def render_prompt(template_str: str, **kwargs: object) -> str:
    template = _environment.from_string(template_str)
    return template.render(**kwargs).strip()
