"""Khởi tạo schema đầu tiên trước khi chạy API/worker."""
from backend.app.config import Settings
from backend.app.database import make_engine
from backend.app.models import Base


def main() -> None:
    engine = make_engine(Settings().database_url)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
