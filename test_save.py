import sys
sys.path.append('d:/4-Zone-Keyboard-RGB-Toolkit/python_app')
from main import RGBControllerApp
from PySide6.QtWidgets import QApplication
import traceback
app = QApplication(sys.argv)
window = RGBControllerApp()
try:
    window.save_settings()
    print('Save Settings OK')
except Exception as e:
    print('SAVE SETTINGS FAILED:')
    traceback.print_exc()
