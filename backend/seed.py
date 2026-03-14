from app.db.session import SessionLocal
from app.models.hospital import Hospital
from app.models.user import User
from passlib.context import CryptContext
# Add these lines to the top of seed.py
from app.models.hospital import Hospital
from app.models.user import User
# Ensure the Doctor model is imported so SQLAlchemy can "see" it
from app.models.doctor import Doctor

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

def seed_data():
    try:
        # 1. Check if Hospital exists, if not, create it
        hospital = db.query(Hospital).filter(Hospital.slug == "arogya-specialty").first()
        
        if not hospital:
            hospital = Hospital(
                name="Arogya Specialty Hospital",
                slug="arogya-specialty",
                is_active=True
            )
            db.add(hospital)
            db.commit()
            db.refresh(hospital)
            print(f"Created new hospital: {hospital.name}")
        else:
            print(f"Hospital already exists: {hospital.name} (ID: {hospital.id})")

        # 2. Check if Admin User exists, if not, create it
        admin_email = "admin@arogya.com"
        user = db.query(User).filter(User.email == admin_email).first()

        if not user:
            admin_user = User(
                email=admin_email,
                hashed_password=pwd_context.hash("admin123"),
                hospital_id=hospital.id,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print(f"Created admin user: {admin_email}")
        else:
            # If user exists, let's update the password to be sure it's admin123
            user.hashed_password = pwd_context.hash("admin123")
            user.hospital_id = hospital.id
            db.commit()
            print(f"Updated existing admin user: {admin_email}")
            
        print("\n✅ Success! Log in with admin@arogya.com / admin123")
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()