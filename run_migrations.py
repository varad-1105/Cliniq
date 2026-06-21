from alembic.config import Config
from alembic import command
import os

cfg = Config(os.path.join(os.path.dirname(__file__), 'alembic.ini'))
cfg.set_main_option('script_location', 'alembic')

# Use app config via env.py which will load the Flask app
command.upgrade(cfg, 'head')
