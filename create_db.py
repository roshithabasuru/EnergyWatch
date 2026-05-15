import sqlalchemy
from sqlalchemy import create_engine, text

engine = create_engine('mysql://root:root@localhost:3306/')
with engine.connect() as conn:
    conn.execute(text("CREATE DATABASE IF NOT EXISTS energywatch CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
print("Database created successfully")
