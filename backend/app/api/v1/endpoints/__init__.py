# Location: D:\Hospital\hospital-ai-platform\backend\app\api\v1\endpoints\__init__.py
from .hospitals import router as hospitals
from .auth import router as auth
from .ai import router as ai
from .appointments import router as appointments
from .usage import router as usage
from .medicines import router as medicines
from .lab_tests import router as lab_tests
from .doctor_availability import router as availability