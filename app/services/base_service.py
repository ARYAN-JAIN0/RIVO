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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        self.close()
