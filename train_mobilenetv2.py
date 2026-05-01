import os
import json
import argparse
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns


CLASSES = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']


def build_model(num_classes: int, pretrained: bool = True) -> nn.Module:
    weights = models.MobileNet_V2_Weights.IMAGENET1K_V1 if pretrained else None
    model = models.mobilenet_v2(weights=weights)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    return model


class FER2013CsvDataset(Dataset):
    def __init__(self, images: np.ndarray, labels: np.ndarray, transform=None):
        self.images = images
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        img = self.images[idx]
        if self.transform is not None:
            img = self.transform(img)
        return img, int(self.labels[idx])


def load_fer2013_csv(csv_path: str):
    df = pd.read_csv(csv_path)
    usage_col = 'Usage' if 'Usage' in df.columns else df.columns[-1]
    pixels_col = 'pixels' if 'pixels' in df.columns else df.columns[1]
    label_col = 'emotion' if 'emotion' in df.columns else df.columns[0]

    def to_img(s):
        arr = np.fromstring(s, dtype=np.uint8, sep=' ')
        return arr.reshape(48, 48)

    print(f'Loading {csv_path} ...')
    imgs = np.stack([to_img(p) for p in df[pixels_col].values])
    labels = df[label_col].values.astype(np.int64)
    usage = df[usage_col].values

    train_mask = usage == 'Training'
    test_mask = (usage == 'PublicTest') | (usage == 'PrivateTest')

    return (imgs[train_mask], labels[train_mask],
            imgs[test_mask], labels[test_mask])


def get_loaders(csv_path: str, img_size: int, batch_size: int, num_workers: int):
    train_imgs, train_labels, test_imgs, test_labels = load_fer2013_csv(csv_path)
    print(f'Train: {len(train_labels)}, Test: {len(test_labels)}')

    train_tf = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((img_size, img_size)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    test_tf = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    train_set = FER2013CsvDataset(train_imgs, train_labels, train_tf)
    test_set = FER2013CsvDataset(test_imgs, test_labels, test_tf)

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True,
                              num_workers=num_workers, pin_memory=True,
                              persistent_workers=num_workers > 0)
    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=False,
                             num_workers=num_workers, pin_memory=True,
                             persistent_workers=num_workers > 0)
    return train_loader, test_loader, CLASSES


def run_epoch(model, loader, criterion, optimizer, device, train: bool):
    model.train() if train else model.eval()
    total_loss, total_correct, total = 0.0, 0, 0
    all_preds, all_labels = [], []

    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for x, y in loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            if train:
                optimizer.zero_grad()
            out = model(x)
            loss = criterion(out, y)
            if train:
                loss.backward()
                optimizer.step()
            total_loss += loss.item() * x.size(0)
            preds = out.argmax(1)
            total_correct += (preds == y).sum().item()
            total += x.size(0)
            if not train:
                all_preds.append(preds.cpu().numpy())
                all_labels.append(y.cpu().numpy())

    avg_loss = total_loss / total
    acc = total_correct / total
    if not train:
        all_preds = np.concatenate(all_preds)
        all_labels = np.concatenate(all_labels)
        return avg_loss, acc, all_preds, all_labels
    return avg_loss, acc


def save_checkpoint(path, model, optimizer, scheduler, epoch, history, best_acc):
    torch.save({
        'epoch': epoch,
        'model_state': model.state_dict(),
        'optimizer_state': optimizer.state_dict(),
        'scheduler_state': scheduler.state_dict() if scheduler is not None else None,
        'history': history,
        'best_acc': best_acc,
    }, path)


def load_checkpoint(path, model, optimizer, scheduler, device):
    ckpt = torch.load(path, map_location=device)
    model.load_state_dict(ckpt['model_state'])
    if optimizer is not None and ckpt.get('optimizer_state') is not None:
        optimizer.load_state_dict(ckpt['optimizer_state'])
    if scheduler is not None and ckpt.get('scheduler_state') is not None:
        scheduler.load_state_dict(ckpt['scheduler_state'])
    return ckpt['epoch'], ckpt.get('history', {}), ckpt.get('best_acc', 0.0)


def plot_curves(history, out_dir):
    epochs = range(1, len(history['train_loss']) + 1)

    plt.figure(figsize=(8, 5))
    plt.plot(epochs, history['train_loss'], label='Train Loss')
    plt.plot(epochs, history['val_loss'], label='Val Loss')
    plt.xlabel('Epoch'); plt.ylabel('Loss'); plt.title('Loss Curve')
    plt.legend(); plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'loss_curve.png'), dpi=150)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(epochs, history['train_acc'], label='Train Acc')
    plt.plot(epochs, history['val_acc'], label='Val Acc')
    plt.xlabel('Epoch'); plt.ylabel('Accuracy'); plt.title('Accuracy Curve')
    plt.legend(); plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'acc_curve.png'), dpi=150)
    plt.close()


def plot_confusion_matrix(y_true, y_pred, classes, out_dir):
    cm = confusion_matrix(y_true, y_pred)
    cm_norm = cm.astype('float') / cm.sum(axis=1, keepdims=True)

    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=classes, yticklabels=classes)
    plt.xlabel('Predicted'); plt.ylabel('True'); plt.title('Confusion Matrix')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'confusion_matrix.png'), dpi=150)
    plt.close()

    plt.figure(figsize=(8, 6))
    sns.heatmap(cm_norm, annot=True, fmt='.2f', cmap='Blues',
                xticklabels=classes, yticklabels=classes)
    plt.xlabel('Predicted'); plt.ylabel('True'); plt.title('Normalized Confusion Matrix')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'confusion_matrix_norm.png'), dpi=150)
    plt.close()


def plot_per_class_acc(y_true, y_pred, classes, out_dir):
    cm = confusion_matrix(y_true, y_pred)
    per_class_acc = cm.diagonal() / cm.sum(axis=1)

    plt.figure(figsize=(8, 5))
    bars = plt.bar(classes, per_class_acc, color='steelblue')
    plt.ylim(0, 1)
    plt.ylabel('Accuracy'); plt.title('Per-Class Accuracy')
    for b, v in zip(bars, per_class_acc):
        plt.text(b.get_x() + b.get_width() / 2, v + 0.01, f'{v:.2f}', ha='center')
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'per_class_acc.png'), dpi=150)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=str, default='fer2013.csv')
    parser.add_argument('--out_dir', type=str, default='runs/mobilenetv2')
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch_size', type=int, default=64)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--weight_decay', type=float, default=1e-4)
    parser.add_argument('--img_size', type=int, default=96)
    parser.add_argument('--num_workers', type=int, default=4)
    parser.add_argument('--resume', action='store_true', help='从 last.pt 继续训练')
    parser.add_argument('--ckpt', type=str, default='', help='指定恢复的检查点路径')
    parser.add_argument('--no_pretrained', action='store_true')
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    last_ckpt = out_dir / 'last.pt'
    best_ckpt = out_dir / 'best.pt'
    history_json = out_dir / 'history.json'

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Device: {device}')

    train_loader, test_loader, classes = get_loaders(
        args.csv, args.img_size, args.batch_size, args.num_workers
    )
    print(f'Classes: {classes}')

    model = build_model(num_classes=len(classes), pretrained=not args.no_pretrained).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    start_epoch = 0
    best_acc = 0.0
    history = {'train_loss': [], 'train_acc': [], 'val_loss': [], 'val_acc': [], 'lr': []}

    resume_path = args.ckpt if args.ckpt else (str(last_ckpt) if args.resume and last_ckpt.exists() else '')
    if resume_path and os.path.exists(resume_path):
        start_epoch, history, best_acc = load_checkpoint(resume_path, model, optimizer, scheduler, device)
        print(f'Resumed from {resume_path}, start_epoch={start_epoch}, best_acc={best_acc:.4f}')

    for epoch in range(start_epoch, args.epochs):
        t0 = time.time()
        tr_loss, tr_acc = run_epoch(model, train_loader, criterion, optimizer, device, train=True)
        val_loss, val_acc, y_pred, y_true = run_epoch(model, test_loader, criterion, optimizer, device, train=False)
        scheduler.step()

        history['train_loss'].append(tr_loss)
        history['train_acc'].append(tr_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        history['lr'].append(optimizer.param_groups[0]['lr'])

        dt = time.time() - t0
        print(f'Epoch {epoch+1}/{args.epochs} | '
              f'train_loss={tr_loss:.4f} train_acc={tr_acc:.4f} | '
              f'val_loss={val_loss:.4f} val_acc={val_acc:.4f} | '
              f'lr={history["lr"][-1]:.2e} | {dt:.1f}s')

        save_checkpoint(last_ckpt, model, optimizer, scheduler, epoch + 1, history, best_acc)
        if val_acc > best_acc:
            best_acc = val_acc
            save_checkpoint(best_ckpt, model, optimizer, scheduler, epoch + 1, history, best_acc)
            print(f'  -> new best: {best_acc:.4f}')

        with open(history_json, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        plot_curves(history, str(out_dir))

    if best_ckpt.exists():
        load_checkpoint(str(best_ckpt), model, None, None, device)
    _, final_acc, y_pred, y_true = run_epoch(model, test_loader, criterion, optimizer, device, train=False)
    print(f'Final best val_acc={final_acc:.4f}')

    plot_confusion_matrix(y_true, y_pred, classes, str(out_dir))
    plot_per_class_acc(y_true, y_pred, classes, str(out_dir))

    report = classification_report(y_true, y_pred, target_names=classes, digits=4)
    with open(out_dir / 'classification_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    print(report)


if __name__ == '__main__':
    main()
