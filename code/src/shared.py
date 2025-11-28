import torch
import torch.nn as nn
from torch.utils.data import Dataset
import json
import re
import os

# --- SHARED CONFIGURATION ---
DATA_FILE = os.path.join("data", "sysmon_data_training.json")
MODEL_PATH = "sysmon_model.pth"
MAX_SEQ_LEN = 120
EMBED_DIM = 64
BATCH_SIZE = 8
LEARNING_RATE = 0.001

# --- 1. SHARED DATASET CLASS ---
class SysmonDataset(Dataset):
    def __init__(self, data_list, max_len=100, vocab=None):
        self.data = data_list
        self.labels = [item.get('label', 0) for item in self.data]
        self.max_len = max_len
        
        self.text_sequences = []
        for item in self.data:
            text = item.get('CommandLine', '')
            if not text:
                text = f"{item.get('Image', '')} {item.get('DestinationIp', '')} {item.get('DestinationPort', '')}"
            if 'Hashes' in item:
                text += f" {item['Hashes']}"
            self.text_sequences.append(text)

        self.tokenized_data = [self.tokenize(txt) for txt in self.text_sequences]
        
        if vocab is None:
            self.vocab = self.build_vocab(self.tokenized_data)
        else:
            self.vocab = vocab
            
    def tokenize(self, text):
        text = str(text).lower()
        return re.findall(r"[\w']+|[.,!?;/\\-]", text)

    def build_vocab(self, all_tokens):
        vocab = {"<PAD>": 0, "<UNK>": 1}
        unique_words = set(token for seq in all_tokens for token in seq)
        for word in unique_words:
            vocab[word] = len(vocab)
        return vocab

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        tokens = self.tokenized_data[idx]
        label = self.labels[idx]
        indices = [self.vocab.get(t, self.vocab["<UNK>"]) for t in tokens]
        
        if len(indices) < self.max_len:
            indices = indices + [0] * (self.max_len - len(indices))
        else:
            indices = indices[:self.max_len]
            
        return torch.tensor(indices, dtype=torch.long), torch.tensor(label, dtype=torch.float)

# --- 2. SHARED MODEL ARCHITECTURE ---
class HybridCNNTransformer(nn.Module):
    def __init__(self, vocab_size, embed_dim=64, use_cnn=True, use_transformer=True):
        super(HybridCNNTransformer, self).__init__()
        self.use_cnn = use_cnn
        self.use_transformer = use_transformer
        
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        
        # --- CNN LAYERS (Now with Kernel 3, 4, AND 5) ---
        self.conv1 = nn.Conv1d(embed_dim, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv1d(embed_dim, 32, kernel_size=4, padding=2)
        # [NEW] Kernel Size 5 (extracts 5-gram patterns)
        self.conv3 = nn.Conv1d(embed_dim, 32, kernel_size=5, padding=2) 
        
        self.pool = nn.MaxPool1d(2)
        self.relu = nn.ReLU()
        
        # Calculate input dim for Transformer
        # If CNN is used, we concat 3 filters of 32 channels = 96 channels
        trans_input = 96 if use_cnn else embed_dim
        
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=trans_input, nhead=4, batch_first=True), 
            num_layers=1
        )
        
        self.fc = nn.Linear(trans_input, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        emb = self.embedding(x) # [batch, seq, dim]
        features = emb
        
        if self.use_cnn:
            emb_t = emb.permute(0, 2, 1) # [batch, dim, seq]
            
            # Apply 3 parallel filters
            c1 = self.pool(self.relu(self.conv1(emb_t)))
            c2 = self.pool(self.relu(self.conv2(emb_t)))
            c3 = self.pool(self.relu(self.conv3(emb_t))) # [NEW]
            
            # Truncate to match the shortest sequence
            min_l = min(c1.shape[2], c2.shape[2], c3.shape[2])
            
            # Concatenate 3 filters (32+32+32 = 96 features)
            features = torch.cat([c1[:,:,:min_l], c2[:,:,:min_l], c3[:,:,:min_l]], dim=1)
            features = features.permute(0, 2, 1) # Back to [batch, seq, dim]
            
        if self.use_transformer:
            features = self.transformer(features)
            
        out = features.mean(dim=1)
        return self.sigmoid(self.fc(out))