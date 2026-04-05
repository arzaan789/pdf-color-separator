import sys
import logging

from PyQt6.QtWidgets import QApplication

from main_window import MainWindow

logging.basicConfig(level=logging.WARNING)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Color Separator")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
