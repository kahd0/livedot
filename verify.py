import sys
import os

print("--- LIVEDOT RUNTIME VERIFICATION ---")

# 1. Test Python environment
print(f"Python interpreter: {sys.executable}")
print(f"Current working dir: {os.getcwd()}")

# 2. Test PyQt6 import
try:
    from PyQt6.QtCore import QObject, QTimer, QSharedMemory
    from PyQt6.QtWidgets import QApplication
    print("[OK] PyQt6 Core and Widgets imported successfully.")
except ImportError as e:
    print(f"[FAIL] PyQt6 import failed: {e}")
    sys.exit(1)

# 3. Test python-xlib import
try:
    from Xlib import X
    from Xlib.display import Display
    print("[OK] python-xlib imported successfully.")
except ImportError as e:
    print(f"[FAIL] python-xlib import failed: {e}")
    sys.exit(1)

# 4. Try connecting to X server
try:
    d = Display()
    print(f"[OK] Successfully connected to X Display: {d.get_display_name()}")
    has_xtest = d.has_extension("XTEST")
    print(f"[OK] XTEST extension available: {has_xtest}")
    d.close()
except Exception as e:
    print(f"[FAIL] Connection to X display failed: {e}")
    print("      Note: If you are running headless, this is expected. But it's required for GUI runtime.")

# 5. Test sound generation
try:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import sound_manager
    import constants
    
    print("Testing programmatic WAV tone generation...")
    sound_manager.initialize_sounds()
    
    if os.path.exists(constants.MUTE_SOUND_FILE):
        print(f"[OK] Generated mute sound at: {constants.MUTE_SOUND_FILE} ({os.path.getsize(constants.MUTE_SOUND_FILE)} bytes)")
    else:
        print("[FAIL] Mute sound file not found after generation.")
        sys.exit(1)
        
    if os.path.exists(constants.UNMUTE_SOUND_FILE):
        print(f"[OK] Generated unmute sound at: {constants.UNMUTE_SOUND_FILE} ({os.path.getsize(constants.UNMUTE_SOUND_FILE)} bytes)")
    else:
        print("[FAIL] Unmute sound file not found after generation.")
        sys.exit(1)
except Exception as e:
    print(f"[FAIL] Sound manager test failed: {e}")
    sys.exit(1)

print("\n[SUCCESS] All code checks and dependencies are correct!")
sys.exit(0)
