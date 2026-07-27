from .rom_manager import ROMManager

def main():
    mgr = ROMManager()
    print("Class instantiated successfully!")
    mgr.scan_devices()

if __name__ == "__main__":
    main()
