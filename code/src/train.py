import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
import json
import os
# Import classes from our shared file
import shared 

EPOCHS = 4

def train_pipeline():
    print("="*40)
    print("      TRAINING PHASE STARTED")
    print("="*40)

    # 1. Load Data
    if not os.path.exists(shared.DATA_FILE):
        print(f"[!] Error: {shared.DATA_FILE} not found.")
        return

    with open(shared.DATA_FILE, 'r') as f:
        full_data = json.load(f)

    # 2. Split Data (Using random_state=42 ensures Evaluation gets the EXACT SAME split)
    train_data, test_data = train_test_split(full_data, test_size=0.3,random_state=42, shuffle=True)
    print(f"[*] Training on {len(train_data)} samples.")

    # 3. Setup Dataset & Model
    train_dataset = shared.SysmonDataset(train_data, max_len=shared.MAX_SEQ_LEN)
    train_loader = DataLoader(train_dataset, batch_size=shared.BATCH_SIZE, shuffle=True)

    model = shared.HybridCNNTransformer(len(train_dataset.vocab))
    optimizer = optim.Adam(model.parameters(), lr=shared.LEARNING_RATE)
    criterion = nn.BCELoss()

    # 4. Training Loop
    model.train()
    for epoch in range(EPOCHS):
        total_loss = 0
        for X, y in train_loader:
            optimizer.zero_grad()
            pred = model(X).squeeze()
            if pred.ndim == 0: pred = pred.unsqueeze(0)
            loss = criterion(pred, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch+1}/{EPOCHS} | Train Loss: {total_loss/len(train_loader):.4f}")

    # 5. Save the Model & Vocab Size
    # We save a dictionary containing the weights AND the vocab size (needed for loading)
    save_info = {
        'state_dict': model.state_dict(),
        'vocab': train_dataset.vocab
    }
    torch.save(save_info, shared.MODEL_PATH)
    print(f"\n[+] Model saved successfully to: {shared.MODEL_PATH}")
    print("[*] You can now run 'python src/evaluate.py'")

if __name__ == "__main__":
    train_pipeline()