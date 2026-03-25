from fastapi.templating import Jinja2Templates
from jinja2 import Environment, PackageLoader

env = Environment(
    loader=PackageLoader("oscilla"),
    autoescape=True,
)
response_templates = Jinja2Templates(directory="oscilla/templates")

# Use the primary environment inside of the Jinja2Templates wrapper.
response_templates.env = env
