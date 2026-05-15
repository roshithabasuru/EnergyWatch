import os
from datetime import datetime
from pymongo import MongoClient

# Initialize MongoDB connection
_mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/energywatch')
_client = MongoClient(_mongo_uri)
_db = _client.get_database()
_audit_collection = _db.audit_logs

class AuditLog:
    def __init__(self, user_id, action, resource_type=None, resource_id=None, details=None, timestamp=None):
        self.user_id = user_id
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.details = details
        self.timestamp = timestamp or datetime.utcnow()

    def save(self):
        doc = {
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "timestamp": self.timestamp
        }
        _audit_collection.insert_one(doc)

    @classmethod
    def get_all(cls):
        # Return sorted by timestamp descending
        cursor = _audit_collection.find().sort("timestamp", -1)
        logs = []
        for doc in cursor:
            log = cls(
                user_id=doc.get("user_id"),
                action=doc.get("action"),
                resource_type=doc.get("resource_type"),
                resource_id=doc.get("resource_id"),
                details=doc.get("details"),
                timestamp=doc.get("timestamp")
            )
            logs.append(log)
        return logs

