from fastapi.templating import Jinja2Templates
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["enumerate"] = enumerate
templates.env.tests["number"] = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
