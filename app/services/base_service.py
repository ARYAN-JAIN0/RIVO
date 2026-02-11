from app.database.db import SessionLocal

class BaseService:
    def __init__(self, db=None):
        self.db = db or SessionLocal()

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()

    def close(self):
        self.db.close()
