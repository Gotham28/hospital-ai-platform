from app.db.base import Base
from app.db.session import engine
# Import all your models here so SQLAlchemy knows they exist
from app.models.hospital import Hospital
from app.models.user import User
from app.models.doctor import Doctor 

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("Tables created successfully!")