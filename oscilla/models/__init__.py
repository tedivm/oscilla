import glob
from os.path import basename, dirname, isfile, join

modules = glob.glob(join(dirname(__file__), "*.py"))
__all__ = [basename(f)[:-3] for f in modules if isfile(f) and not f.endswith("__init__.py")]

# Explicit imports ensure Alembic autogenerate sees all models via `from oscilla.models import *`
from oscilla.models import base  # noqa: E402, F401
from oscilla.models.character import CharacterRecord  # noqa: E402, F401
from oscilla.models.character_iteration import (  # noqa: E402, F401
    CharacterIterationEquipment,
    CharacterIterationInventory,
    CharacterIterationMilestone,
    CharacterIterationQuest,
    CharacterIterationRecord,
    CharacterIterationStatistic,
    CharacterIterationStatValue,
)
from oscilla.models.user import UserRecord  # noqa: E402, F401
