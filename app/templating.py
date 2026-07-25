"""Template engine setup — isolated module to avoid circular imports."""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
