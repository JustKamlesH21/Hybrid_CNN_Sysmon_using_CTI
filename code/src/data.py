import json
import random
import os

def merge():
    print("[*] Merging datasets...")
    
    # Load Real
    try:
        with open("data/sysmon_data_real.json", "r") as f:
            real = json.load(f)
    except FileNotFoundError:
        print("[!] Error: Run collector.py first!")
        return

    # Load Synthetic
    try:
        with open("data/sysmon_data_synthetic.json", "r") as f:
            fake = json.load(f)
    except FileNotFoundError:
        print("[!] Error: Run logic_trap.py first!")
        return

    # Combine
    combined = real + fake
    random.shuffle(combined)
    
    # Save
    with open("data/sysmon_data_training.json", "w") as f:
        json.dump(combined, f, indent=4)
        
    print(f"[+] SUCCESS. Final Training Set: {len(combined)} samples.")
    print(f"[+] Location: data/sysmon_data_training.json")

if __name__ == "__main__":
    merge()