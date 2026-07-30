import json, os
import xml.etree.ElementTree as ET
from glob import glob
from hashlib import file_digest
from pathlib import Path


# Update this path to where your shared ROM directories live
ROM_ROOT = Path('/run/media/SN01T/emudeck/Emulation/roms/')

# Map architectures to their valid file extensions
ARCH_MAP = {
    'gb': ['.gb'],
    'gbc': ['.gbc'],
    'gba': ['.gba'],
    'nds': ['.nds'],
    '3ds': ['.3ds', '.cia'],
    'nes': ['.nes'],
    'snes': ['.smc', '.sfc']
}

# Define your directory mapping layout
DIR_MAPPING = {
    'gb': 'gb',
    'gbc': 'gb',
    'gba': 'gb',
    'nds': 'nds',
    '3ds': '3ds',
    'nes': 'nes',
    'snes': 'snes'
}

rom_sets = {}
rom_lookup = {}

def load_dat_into_memory():
    """
    Builds a fast O(1) memory lookup table: {md5_hash: clean_name}
    """
    md5_lookup_table = {}
    
    for dat_file_path in glob("config/game_dats/*.dat"):
        print(f'Loading {dat_file_path}...')
        try:
            tree = ET.parse(dat_file_path)
            root = tree.getroot()
            for game in root.findall('game'):
                game_name = game.get('name')
                for rom in game.findall('rom'):
                    md5_val = rom.get('md5')
                    if md5_val:
                        md5_lookup_table[md5_val.lower()] = game_name
        except Exception as e:
            print(f"Failed parsing index mapping data: {e}")
    return md5_lookup_table

def get_file_md5(file_path):
    # Initialize the md5 hash object
    md5_hash = md5()
    
    # Open the file in binary read mode ('rb')
    with open(file_path, "rb") as f:
        # Read the file in 8KB chunks
        for chunk in iter(lambda: f.read(8192), b""):
            md5_hash.update(chunk)
            
    # Return the final hexadecimal string
    return md5_hash.hexdigest()


rom_lookup = load_dat_into_memory()

if ROM_ROOT.exists():
    for arch, folder_name in DIR_MAPPING.items():
        target_dir = ROM_ROOT / folder_name
        if target_dir.is_dir():
            valid_exts = ARCH_MAP[arch]
            rom_list = []

            # Recursively walk through all files and subdirectories
            for file_path in target_dir.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in valid_exts:
                    # Skip hidden system or folder metadata files
                    if any(part.startswith('.') for part in file_path.parts):
                        continue

                    # Calculate the relative path from the designated architecture folder root
                    relative_str = str(file_path.relative_to(target_dir))

                    # Optional: Use the parent directory name as a smart series guess
                    parent_name = file_path.parent.name
                    series_guess = parent_name if parent_name != folder_name else 'Uncategorized'

                    # hash identification
                    with open(file_path, "rb") as f:
                        md5_hash = file_digest(f, "md5").hexdigest()

                    print(file_path)
                    print(md5_hash)
                    if md5_hash in rom_lookup:
                        print(rom_lookup[md5_hash])

                    rom_list.append({
                        'path': relative_str,
                        'series': series_guess,
                        'hash': md5_hash,
                        'isCustom': md5_hash not in rom_lookup
                    })

            if rom_list:
                if arch not in rom_sets:
                    rom_sets[arch] = []
                rom_sets[arch].extend(rom_list)

# Transform the dictionary back into the final required manifest array
final_sets = [{'architecture': arch, 'roms': roms} for arch, roms in rom_sets.items()]

output_path = Path('config/roms/default.json')
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps({'romSets': final_sets}, indent=2))
print(f'Successfully built sub-directories manifest inside {output_path}!')
