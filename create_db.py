"""Compatibility entry point for the original course's database setup step."""

from app import app, db


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    print("Database tables are ready. Existing tasks were kept.")
