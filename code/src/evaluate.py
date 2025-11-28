import torch
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import json
import os
import time
import numpy as np
import matplotlib.pyplot as plt
import shared

def evaluate_pipeline():
    print("="*40)
    print("      EVALUATION & VISUALIZATION STARTED")
    print("="*40)

    # 1. Check for Saved Model
    if not os.path.exists(shared.MODEL_PATH):
        print(f"[!] Error: Model file '{shared.MODEL_PATH}' not found.")
        print("    Run 'python src/train.py' first!")
        return
    
    # 2. Load Data & Split
    with open(shared.DATA_FILE, 'r') as f:
        full_data = json.load(f)
    
    # [NEW] Add "Line Number" tracking before shuffling/splitting
    # This helps you find the exact line in your JSON file later.
    for idx, item in enumerate(full_data):
        # JSON is a list, so line number is roughly (index * lines_per_item) + header
        # We just store the index for reference.
        item['original_index'] = idx 

    # Ensure this matches train.py split!
    train_data, test_data = train_test_split(full_data, test_size=0.3, random_state=42, shuffle=True)
    print(f"[*] Evaluating on {len(test_data)} UNSEEN samples.")

    # 3. Load Model Weights
    print(f"[-] Loading model from {shared.MODEL_PATH}...")
    checkpoint = torch.load(shared.MODEL_PATH)
    saved_vocab = checkpoint['vocab']
    id_to_word = {v: k for k, v in saved_vocab.items()}
    
    # 4. Create Test Dataset
    test_dataset = shared.SysmonDataset(test_data, max_len=shared.MAX_SEQ_LEN, vocab=saved_vocab)
    test_loader = DataLoader(test_dataset, batch_size=shared.BATCH_SIZE, shuffle=False)

    # 5. Rebuild Model
    model = shared.HybridCNNTransformer(len(saved_vocab))
    model.load_state_dict(checkpoint['state_dict'])
    model.eval()

    # --- METRICS EVALUATION ---
    all_preds = []
    all_labels = []
    
    # [NEW] List to store details of malicious detections
    malicious_detections = []
    
    print("\n[-] Running Inference...")
    with torch.no_grad():
        for batch_idx, (X, y) in enumerate(test_loader):
            pred = model(X).squeeze()
            if pred.ndim == 0: pred = pred.unsqueeze(0)
            
            # Convert probabilities to 0 or 1
            predicted_classes = (pred > 0.5).float()
            
            # [NEW] Identify Malicious Samples in this Batch
            for i, p_class in enumerate(predicted_classes):
                if p_class == 1: # Model says: MALICIOUS
                    # Find the specific sample in test_data
                    global_idx = batch_idx * shared.BATCH_SIZE + i
                    if global_idx < len(test_data):
                        sample = test_data[global_idx]
                        malicious_detections.append({
                            "test_id": global_idx,
                            "original_json_index": sample.get('original_index'),
                            "confidence": pred[i].item(),
                            "command": sample.get('CommandLine', '')
                        })

            all_preds.extend(predicted_classes.tolist())
            all_labels.extend(y.tolist())

    print("\n[Confusion Matrix]")
    print(confusion_matrix(all_labels, all_preds))
    print("\n[Metrics]")
    print(classification_report(all_labels, all_preds, target_names=['Normal', 'Malicious']))

    # --- [NEW] MALICIOUS DETECTIONS REPORT ---
    print("\n" + "="*80)
    print(f"{'DETECTED THREATS REPORT':^80}")
    print("="*80)
    print(f"{'TestID':<8} | {'JSON Idx':<8} | {'Conf.':<6} | {'Command (Truncated)'}")
    print("-" * 80)
    
    for item in malicious_detections:
        # Show top 50 chars of command
        cmd_short = (item['command'][:50] + '..') if len(item['command']) > 50 else item['command']
        print(f"{item['test_id']:<8} | {item['original_json_index']:<8} | {item['confidence']:.2f}   | {cmd_short}")
        
    print("-" * 80)
    print(f"Total Malicious Objects Detected: {len(malicious_detections)}")

    # --- SPEED TEST ---
    print("\n[Performance Test]")
    dummy_input = torch.randint(0, len(saved_vocab), (100, shared.MAX_SEQ_LEN))
    start_time = time.time()
    with torch.no_grad():
        _ = model(dummy_input)
    end_time = time.time()
    total_time = end_time - start_time
    print(f"Speed: {100/total_time:.2f} logs/second (Processed 100 logs in {total_time:.4f}s)")

    # --- SALIENCY MAP VISUALIZATION ---
    print("\n[Visualization] Generating Saliency Map...")
    
    malicious_samples = [d for d in full_data if d['label'] == 1]
    if not malicious_samples:
        print("[!] No malicious samples found to visualize.")
        return

    sample = malicious_samples[0]
    print(f"Visualizing: {sample['CommandLine'][:60]}...")

    ds = shared.SysmonDataset([sample], max_len=shared.MAX_SEQ_LEN, vocab=saved_vocab)
    input_tensor, _ = ds[0]
    input_tensor = input_tensor.unsqueeze(0)

    model.embedding.weight.requires_grad = True
    model.zero_grad()
    
    output = model(input_tensor)
    output.backward()
    
    grads = model.embedding.weight.grad[input_tensor[0]].abs().sum(dim=1)
    grads = (grads - grads.min()) / (grads.max() - grads.min())
    grads = grads.detach().numpy()

    tokens = [id_to_word.get(idx.item(), "") for idx in input_tensor[0]]
    active_len = len([t for t in tokens if t != "<PAD>"])
    
    plt.figure(figsize=(12, 4))
    plt.bar(range(active_len), grads[:active_len], color='red')
    plt.xticks(range(active_len), tokens[:active_len], rotation=90)
    plt.title(f"AI Attention: Which words triggered the detection?\nCommand: {sample['CommandLine'][:40]}...")
    plt.ylabel("Importance Score")
    plt.tight_layout()
    plt.savefig("saliency_map.png")
    print("[+] Saliency map saved to 'saliency_map.png'")

if __name__ == "__main__":
    evaluate_pipeline()