import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from dotenv import load_dotenv  # ### NEW: Import dotenv

# ### NEW: Add the project root to the path so we can import 'app'
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# ### NEW: Load environment variables from .env
load_dotenv()

# ### NEW: Import your Base model so Alembic can see your tables!
# Change 'app.db.base' to wherever your SQLAlchemy Base is defined.
# If you don't have a Base yet, keep it as None, but you MUST update this later.
try:
    from app.db.base import Base
    target_metadata = Base.metadata
except ImportError:
    target_metadata = None
    print("WARNING: Could not import app.db.base.Base. Autogenerate will not work.")

# this is the Alembic Config object
config = context.config

# ### NEW: Overwrite the sqlalchemy.url in the config with the one from .env
# We use the SYNC driver (psycopg2) for migrations, not the ASYNC one.
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise ValueError("DATABASE_URL not found in .env file!")
config.set_main_option("sqlalchemy.url", db_url)


# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    # ### NEW: We must ensure the engine uses the config we just updated
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()