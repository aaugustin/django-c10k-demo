# Emulate runserver...
from django.core.management.commands.runserver import *

# ... and monkey-patch it!
from django.core.management.commands import runserver
from c10ktools.servers.tulip import run
runserver.run = run
del runserver
