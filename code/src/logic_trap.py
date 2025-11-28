import json
import random
import os

OUTPUT_FILE = os.path.join("data", "sysmon_data_synthetic.json")
SAMPLES = 500

# TRAP: Both sequences have the same words. Only order differs.
# CNN sees "Average(Words)". Transformer sees "Order(Words)".
TOKEN_START = "PROCESS_INITIATE_VALIDATION"
TOKEN_END   = "PROCESS_TERMINATE_SUCCESS" 

def get_noise():
    words = ["thread", "handle", "memory", "virtual", "address", "stack", "heap"]
    return " ".join(random.choices(words, k=40))

def generate():
    if not os.path.exists("data"): os.makedirs("data")
    logs = []
    print(f"[*] Generating {SAMPLES} Logic-Trap samples...")

    for _ in range(SAMPLES):
        noise = get_noise()
        is_malicious = random.choice([True, False])
        
        if is_malicious:
            # MALICIOUS: End comes BEFORE Start (Impossible in reality)
            cmd = f"{TOKEN_END} {noise} {TOKEN_START}"
            label = 1
            desc = "Anomalous process lifecycle: Termination precedes Initialization."
        else:
            # BENIGN: Start comes BEFORE End (Normal)
            cmd = f"{TOKEN_START} {noise} {TOKEN_END}"
            label = 0
            desc = "Standard process lifecycle."

        logs.append({
            "CommandLine": cmd,
            "mitre_id": "SYNTHETIC_TRAP",
            "mitre_name": "Logic Trap Sequence",
            "mitre_desc": desc,
            "label": label
        })

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(logs, f, indent=4)
    print(f"[+] Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    generate()