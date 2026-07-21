import os
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.hospital import Hospital
from app.models.user import User
import app.db.base
from app.models.lab_test import LabTest
from app.models.medicine import Medicine
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

def seed_rich_data():
    try:
        print("Creating superadmin user...")
        # 1. Create superadmin
        superadmin_email = "superadmin@gothos.com"
        sa_user = db.query(User).filter(User.email == superadmin_email).first()
        if not sa_user:
            sa_user = User(
                email=superadmin_email,
                hashed_password=pwd_context.hash("superadmin123"),
                hospital_id=None,
                role="superadmin",
                is_superuser=True,
                is_active=True
            )
            db.add(sa_user)
            db.commit()
            print("Superadmin created: superadmin@gothos.com / superadmin123")
        else:
            print("Superadmin already exists.")

        print("Creating hospitals...")
        # 2. Create hospitals
        hospitals_data = [
            {"name": "TEST - Iris Clone (LOCAL ONLY)", "slug": "test-iris-clone-local"},
            {"name": "City Central Hospital", "slug": "city-central"}
        ]
        hospitals = {}
        for h_data in hospitals_data:
            h = db.query(Hospital).filter(Hospital.slug == h_data["slug"]).first()
            if not h:
                h = Hospital(name=h_data["name"], slug=h_data["slug"], is_active=True)
                db.add(h)
                db.commit()
                db.refresh(h)
            hospitals[h_data["slug"]] = h

        iris = hospitals["test-iris-clone-local"]
        city = hospitals["city-central"]

        print("Creating lab tests...")
        # 3. Create lab tests for Iris
        iris_tests = [
            LabTest(hospital_id=iris.id, name="Rheumatoid Factor (RF) Panel", category="Immunology", price=1500.00, prerequisites="No fasting required", is_inhouse=True, is_outsourced=False),
            LabTest(hospital_id=iris.id, name="Anti-CCP Antibody", category="Immunology", price=2200.00, prerequisites="No fasting", is_inhouse=False, is_outsourced=True, outsourced_note="Sent to Dr. Lal PathLabs"),
            LabTest(hospital_id=iris.id, name="Complete Blood Count (CBC)", category="Hematology", price=450.00, prerequisites="None", is_inhouse=True, is_outsourced=False)
        ]
        for t in iris_tests:
            db.add(t)

        # Lab tests for City Central
        city_tests = [
            LabTest(hospital_id=city.id, name="Comprehensive Metabolic Panel", category="Biochemistry", price=1200.00, prerequisites="8 hrs fasting", is_inhouse=True, is_outsourced=False),
            LabTest(hospital_id=city.id, name="MRI Brain (Contrast)", category="Imaging", price=8500.00, prerequisites="Creatinine test required beforehand", is_inhouse=False, is_outsourced=True, outsourced_note="Partnered Imaging Center")
        ]
        for t in city_tests:
            db.add(t)

        print("Creating pharmacy data...")
        # 4. Create pharmacy data for Iris
        iris_meds = [
            Medicine(hospital_id=iris.id, name="Methotrexate 15mg", category="DMARD", stock_status="in_stock", price=45.0, requires_prescription=True),
            Medicine(hospital_id=iris.id, name="Hydroxychloroquine 200mg", category="DMARD", stock_status="in_stock", price=25.0, requires_prescription=True),
            Medicine(hospital_id=iris.id, name="Prednisolone 5mg", category="Corticosteroid", stock_status="low_stock", price=10.0, requires_prescription=True)
        ]
        for m in iris_meds:
            db.add(m)

        # Pharmacy data for City Central
        city_meds = [
            Medicine(hospital_id=city.id, name="Paracetamol 500mg", category="Analgesic", stock_status="in_stock", price=2.0, requires_prescription=False),
            Medicine(hospital_id=city.id, name="Amoxicillin 500mg", category="Antibiotic", stock_status="out_of_stock", price=12.0, requires_prescription=True)
        ]
        for m in city_meds:
            db.add(m)

        db.commit()
        print("Done seeding rich data.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    seed_rich_data()
