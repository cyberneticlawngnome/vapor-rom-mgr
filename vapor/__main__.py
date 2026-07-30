from .rom_manager import ROMManager

def main():
    mgr = ROMManager()
    print("Class instantiated successfully!")
    mgr.detect_devices()

if __name__ == "__main__":
    main()
