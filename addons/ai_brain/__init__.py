try:
    from . import models as models
    from . import controllers as controllers
except ModuleNotFoundError as exc:
    if exc.name != "odoo":
        raise


__all__ = ["models", "controllers"]
