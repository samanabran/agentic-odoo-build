# addons/ai_brain/tests/__init__.py
try:
    import odoo  # noqa: F401
except ModuleNotFoundError:
    odoo = None

if odoo is not None:
    from . import test_classical_inheritance as test_classical_inheritance
    from . import test_dashboard_controller as test_dashboard_controller

from . import test_matching_engine as test_matching_engine

__all__ = [
    "test_classical_inheritance",
    "test_dashboard_controller",
    "test_matching_engine",
]
