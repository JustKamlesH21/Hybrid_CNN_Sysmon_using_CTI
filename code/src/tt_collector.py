import win32evtlog
import xml.etree.ElementTree as ET
import json
import time
import os
import sys
import re
import requests

# --- CONFIGURATION ---
OUTPUT_FILE = os.path.join("data", "sysmon_data_real.json")
COLLECTION_DURATION_MINUTES = 5
SYSMON_CHANNEL = "Microsoft-Windows-Sysmon/Operational"
MITRE_CTI_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"

class MitreAttackAPI:
    """Connects to MITRE GitHub to fetch live Threat Intelligence."""
    def __init__(self):
        self.techniques = {} 
        self.load_mitre_data()

    def load_mitre_data(self):
        print("[*] Connecting to MITRE CTI API...")
        try:
            response = requests.get(MITRE_CTI_URL)
            stix_data = response.json()
            print("[*] Download complete. Indexing...")
            
            for obj in stix_data.get("objects", []):
                if obj.get("type") == "attack-pattern":
                    mitre_id = None
                    for ref in obj.get("external_references", []):
                        if ref.get("source_name") == "mitre-attack":
                            mitre_id = ref.get("external_id")
                            break
                    if mitre_id:
                        self.techniques[mitre_id] = {
                            "name": obj.get("name"),
                            "desc": obj.get("description", "No description.")
                        }
            print(f"[*] Indexed {len(self.techniques)} Techniques.")
        except Exception as e:
            print(f"[!] API Error: {e}")

    def get_details(self, tid):
        return self.techniques.get(tid, {"name": "Unknown", "desc": ""})

class CTIEnricher:
    def __init__(self):
        self.api = MitreAttackAPI()
        # The 'Trigger' List: Maps Regex -> MITRE ID
        self.rules = [
            {"id": "T1059.001", "pattern": r"(powershell|pwsh|invoke-)"},
            {"id": "T1059.003", "pattern": r"(cmd\.exe|/c|/k)"},
            {"id": "T1033",     "pattern": r"(whoami|quser)"},
            {"id": "T1057",     "pattern": r"(tasklist|qprocess)"},
            {"id": "T1016",     "pattern": r"(ipconfig|netsh|route print)"},
            {"id": "T1003",     "pattern": r"(mimikatz|lsass|procdump)"},
            {"id": "T1105",     "pattern": r"(certutil|curl|wget)"},
        ]

    def enrich(self, cmd):
        if not cmd: return None
        cmd_lower = cmd.lower()
        
        # Default = Benign (Label 0)
        res = {"mitre_id": "Benign", "mitre_name": "Normal", "mitre_desc": "", "label": 0}

        for rule in self.rules:
            if re.search(rule["pattern"], cmd_lower):
                tid = rule["id"]
                details = self.api.get_details(tid)
                # Detection = Suspicious (Label 1)
                res = {
                    "mitre_id": tid,
                    "mitre_name": details["name"],
                    "mitre_desc": details["desc"][:200], # Truncate for cleanliness
                    "label": 1 
                }
                break
        return res

def get_sysmon_logs():
    if not os.path.exists("data"): os.makedirs("data")
    
    # 1. Init API
    cti = CTIEnricher()
    
    print("="*50)
    print(f"[*] STARTING COLLECTION ({COLLECTION_DURATION_MINUTES} mins)")
    print("="*50)

    start = time.time()
    end = start + (COLLECTION_DURATION_MINUTES * 60)
    logs = []
    
    try:
        h = win32evtlog.EvtQuery(SYSMON_CHANNEL, win32evtlog.EvtQueryChannelPath, "*[System[(EventID=1)]]")
    except:
        print("[!] Error: Run as Administrator or check Sysmon install.")
        return

    while True:
        if time.time() > end: break
        events = win32evtlog.EvtNext(h, 10)
        
        if not events:
            time.sleep(1)
            continue
            
        for e in events:
            try:
                xml = win32evtlog.EvtRender(e, 1)
                root = ET.fromstring(xml)
                ns = {'n': 'http://schemas.microsoft.com/win/2004/08/events/event'}
                data = {d.attrib['Name']:d.text for d in root.findall('.//n:Data', ns)}
                
                cmd = data.get("CommandLine")
                if cmd:
                    # 2. Enrich with CTI
                    meta = cti.enrich(cmd)
                    
                    entry = {
                        "CommandLine": cmd,
                        "mitre_id": meta["mitre_id"],
                        "mitre_name": meta["mitre_name"], # Used by Transformer
                        "mitre_desc": meta["mitre_desc"], # Used by Transformer
                        "label": meta["label"]
                    }
                    logs.append(entry)
                    sys.stdout.write(f"\r[*] Captured: {len(logs)}")
            except: continue

    with open(OUTPUT_FILE, 'w') as f: json.dump(logs, f, indent=4)
    print(f"\n[+] Saved {len(logs)} real events to {OUTPUT_FILE}")

if __name__ == "__main__":
    get_sysmon_logs()