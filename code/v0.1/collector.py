import win32evtlog
import xml.etree.ElementTree as ET
import json
import time
import os
import sys

# --- CONFIGURATION ---
OUTPUT_FILE = os.path.join("data", "sysmon_data_raw.json")
COLLECTION_DURATION_MINUTES = 5
SYSMON_CHANNEL = "Microsoft-Windows-Sysmon/Operational"

# We now collect Process Create (1) AND Network Connect (3)
XPATH_QUERY = "*[System[(EventID=1) or (EventID=3)]]"

def ensure_dirs():
    if not os.path.exists("data"):
        os.makedirs("data")

def is_admin():
    try:
        return os.getuid() == 0
    except AttributeError:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0

def get_sysmon_logs():
    ensure_dirs()
    
    print("="*60)
    print(f"[*] ENHANCED SYSMON COLLECTOR STARTED")
    print(f"[*] Duration: {COLLECTION_DURATION_MINUTES} minutes")
    print(f"[*] Collecting: Process Creation (ID 1) & Network Connections (ID 3)")
    print("="*60)

    if not is_admin():
        print("[!] ERROR: Script is not running as Administrator.")
        return

    start_time = time.time()
    end_time = start_time + (COLLECTION_DURATION_MINUTES * 60)
    logs = []
    
    try:
        query_handle = win32evtlog.EvtQuery(
            SYSMON_CHANNEL,
            win32evtlog.EvtQueryChannelPath,
            XPATH_QUERY
        )
    except Exception as e:
        print(f"[!] CRITICAL ERROR: {e}")
        return

    count = 0
    print("[*] Listening for events... (Open Chrome, run PowerShell, etc.)")
    
    try:
        while True:
            current_time = time.time()
            remaining = int(end_time - current_time)
            
            if remaining <= 0:
                print("\n[*] Time limit reached.")
                break
                
            events = win32evtlog.EvtNext(query_handle, 10)
            
            if len(events) == 0:
                sys.stdout.write(f"\r[*] Time Remaining: {remaining}s | Captured: {count}")
                sys.stdout.flush()
                time.sleep(1)
                continue

            for event in events:
                xml_content = win32evtlog.EvtRender(event, win32evtlog.EvtRenderEventXml)
                try:
                    root = ET.fromstring(xml_content)
                    ns = {'ns': 'http://schemas.microsoft.com/win/2004/08/events/event'}
                    
                    # 1. Get Event ID
                    system_tag = root.find('ns:System', ns)
                    event_id = system_tag.find('ns:EventID', ns).text
                    
                    # 2. Get Event Data
                    event_data = root.find('ns:EventData', ns)
                    if event_data is None: continue
                    
                    # Parse all fields into a dict
                    raw_data = {}
                    for data in event_data.findall('ns:Data', ns):
                        name = data.attrib.get('Name')
                        if name and data.text:
                            raw_data[name] = data.text

                    # 3. Build Rich Log Entry
                    # We combine relevant fields depending on the Event Type
                    clean_entry = {
                        "EventID": event_id,
                        "Image": raw_data.get("Image", "Unknown"),
                        "User": raw_data.get("User", "Unknown"),
                        "label": 0
                    }

                    if event_id == "1": # Process Creation
                        clean_entry["CommandLine"] = raw_data.get("CommandLine", "")
                        clean_entry["ParentImage"] = raw_data.get("ParentImage", "")
                        clean_entry["Hashes"] = raw_data.get("Hashes", "")
                        clean_entry["IntegrityLevel"] = raw_data.get("IntegrityLevel", "")
                        
                    elif event_id == "3": # Network Connection
                        # Network events don't have CommandLine, so we assume the Image is the 'command'
                        clean_entry["CommandLine"] = "" 
                        clean_entry["DestinationIp"] = raw_data.get("DestinationIp", "")
                        clean_entry["DestinationPort"] = raw_data.get("DestinationPort", "")
                        clean_entry["Protocol"] = raw_data.get("Protocol", "")

                    logs.append(clean_entry)
                    count += 1
                        
                except Exception:
                    continue

    except KeyboardInterrupt:
        print("\n[*] Collection stopped manually.")

    print(f"\n[*] Complete. Saved {len(logs)} rich events to {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(logs, f, indent=4)

if __name__ == "__main__":
    get_sysmon_logs()