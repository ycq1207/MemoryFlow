import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.home_window import HomeWindow
from app.core.database import Database


def create_directories():
    """创建程序运行所需目录"""

    folders = [
        "database",
        "poems",
        "assets",
        "logs"
    ]

    base = Path(__file__).parent

    for folder in folders:
        (base / folder).mkdir(exist_ok=True)


def main():

    create_directories()

    app = QApplication(sys.argv)

    app.setApplicationName("MemoryFlow")
    app.setApplicationVersion("0.1.0")

    db = Database()

    window = HomeWindow(db)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()