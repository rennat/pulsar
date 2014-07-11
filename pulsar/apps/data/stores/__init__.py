# Register battery-included data-stores
from .redis import *
from .pulsards import *
from .couchdb import *

try:
    from .sql import *
except ImportError:
    pass
