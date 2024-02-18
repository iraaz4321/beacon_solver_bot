import os
import pickle

from PIL import Image
import imagehash

beacon_location = "beaconImages"

def calculate_hash(file_name):
    hash_value = imagehash.crop_resistant_hash(Image.open(beacon_location + "/" + file_name))
    return file_name, hash_value


def calculate_hashes():
    hash_dict = {}
    # Calculate and store hashes for each image in the directory
    total_files = len(os.listdir(beacon_location))
    for i, filename in enumerate(os.listdir(beacon_location)):
        print(f"Hashes handled {i+1}/{total_files}")
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            name, hash_res = calculate_hash(filename)
            hash_dict[hash_res] = name

    filehandler = open("beacons.starscape", 'wb')
    pickle.dump(hash_dict, filehandler)