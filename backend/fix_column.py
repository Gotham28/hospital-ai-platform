import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS entry_type VARCHAR DEFAULT 'fact'")
conn.commit()
cur.close()
conn.close()
print('Done!')