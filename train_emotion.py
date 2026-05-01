import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
import random
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, models, transforms
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DATA_DIR = 'fer2013'
TRAIN_DIR = os.path.join(DATA_DIR, 'train')
VAL_DIR = os.path.join(DATA_DIR, 'test')
LABELS = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
NUM_CLASSES = len(LABELS)
BATCH = 64
EPOCHS = 80
PATIENCE = 15
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('Using device:', DEVICE)

data_transforms = {
    'train': transforms.Compose([
        transforms.Resize(288),
        transforms.RandomCrop(224),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(p=0.2),
        transforms.RandomRotation(20),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3, hue=0.1),
        transforms.RandomAffine(degrees=0, translate=(0.1, 0.1), scale=(0.85, 1.15)),
        transforms.RandomGrayscale(p=0.1),
        transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 2.0)),
        transforms.ToTensor(),
        transforms.RandomErasing(p=0.3, scale=(0.02, 0.2)),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ]),
    'val': transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
}


def remap_classes(ds, target_labels):
    name_to_target = {n: i for i, n in enumerate(target_labels)}
    mapping = [name_to_target[c] for c in ds.classes]
    ds.samples = [(p, mapping[t]) for p, t in ds.samples]
    ds.targets = [mapping[t] for t in ds.targets]
    return ds


class CutMixCollator:
    def __init__(self, alpha=1.0, prob=0.5):
        self.alpha = alpha
        self.prob = prob

    def __call__(self, batch):
        images, labels = zip(*batch)
        images = torch.stack(images)
        labels = torch.tensor(labels)
        if random.random() < self.prob:
            lam = np.random.beta(self.alpha, self.alpha)
            batch_size = images.size(0)
            indices = torch.randperm(batch_size)
            _, _, h, w = images.shape
            cx = np.random.uniform(0, w)
            cy = np.random.uniform(0, h)
            rw = w * np.sqrt(1 - lam) / 2
            rh = h * np.sqrt(1 - lam) / 2
            x1 = int(max(cx - rw, 0))
            x2 = int(min(cx + rw, w))
            y1 = int(max(cy - rh, 0))
            y2 = int(min(cy + rh, h))
            images[:, :, y1:y2, x1:x2] = images[indices, :, y1:y2, x1:x2]
            lam = 1 - (y2 - y1) * (x2 - x1) / (h * w)
            return images, labels, labels[indices], lam
        return images, labels, labels, 1.0


def main():
    train_ds = datasets.ImageFolder(TRAIN_DIR, transform=data_transforms['train'])
    val_ds = datasets.ImageFolder(VAL_DIR, transform=data_transforms['val'])
    remap_classes(train_ds, LABELS)
    remap_classes(val_ds, LABELS)

    cutmix = CutMixCollator(alpha=1.0, prob=0.5)
    train_loader = DataLoader(train_ds, batch_size=BATCH, shuffle=True, num_workers=0, pin_memory=True, collate_fn=cutmix)
    val_loader = DataLoader(val_ds, batch_size=BATCH, shuffle=False, num_workers=0, pin_memory=True)

    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    for param in model.parameters():
        param.requires_grad = True
    model.fc = nn.Sequential(
        nn.Dropout(0.4),
        nn.Linear(2048, 512),
        nn.ReLU(inplace=True),
        nn.Dropout(0.2),
        nn.Linear(512, NUM_CLASSES)
    )
    model = model.to(DEVICE)

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

    early_params, layer3_params, layer4_params, fc_params = [], [], [], []
    for name, param in model.named_parameters():
        if 'fc' in name:
            fc_params.append(param)
        elif 'layer4' in name:
            layer4_params.append(param)
        elif 'layer3' in name:
            layer3_params.append(param)
        else:
            early_params.append(param)

    optimizer = optim.AdamW([
        {'params': early_params, 'lr': 2e-6},
        {'params': layer3_params, 'lr': 1e-5},
        {'params': layer4_params, 'lr': 5e-5},
        {'params': fc_params, 'lr': 5e-4},
    ], weight_decay=1e-3)

    scheduler = optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr=[2e-5, 1e-4, 5e-4, 5e-3],
        epochs=EPOCHS,
        steps_per_epoch=len(train_loader),
        pct_start=0.1,
        anneal_strategy='cos'
    )

    hist = {k: [] for k in ['train_loss', 'val_loss', 'train_acc', 'val_acc', 'precision', 'recall', 'f1', 'lr']}
    best_acc = 0.0
    patience_counter = 0

    for epoch in range(EPOCHS):
        model.train()
        train_loss_sum = 0.0
        train_correct = 0
        train_total = 0
        torch.cuda.empty_cache()

        for images, labels_a, labels_b, lam in train_loader:
            images = images.to(DEVICE)
            labels_a = labels_a.to(DEVICE)
            labels_b = labels_b.to(DEVICE)
            outputs = model(images)
            loss = lam * criterion(outputs, labels_a) + (1 - lam) * criterion(outputs, labels_b)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()

            train_loss_sum += loss.item() * images.size(0)
            pred = outputs.detach().argmax(1)
            train_correct += ((pred == labels_a).float() * lam + (pred == labels_b).float() * (1 - lam)).sum().item()
            train_total += images.size(0)

        cur_lr = optimizer.param_groups[-1]['lr']
        hist['train_loss'].append(train_loss_sum / train_total)
        hist['train_acc'].append(train_correct / train_total)
        hist['lr'].append(cur_lr)

        model.eval()
        val_loss_sum = 0.0
        val_correct = 0
        val_total = 0
        cm = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.int64)
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(DEVICE), labels.to(DEVICE)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss_sum += loss.item() * images.size(0)
                pred = outputs.argmax(1)
                val_correct += (pred == labels).sum().item()
                val_total += labels.size(0)
                for t_, p_ in zip(labels.cpu().numpy(), pred.cpu().numpy()):
                    cm[t_, p_] += 1

        acc = val_correct / val_total
        tp = np.diag(cm).astype(np.float64)
        fp = cm.sum(0) - tp
        fn = cm.sum(1) - tp
        prec_per = np.where(tp + fp > 0, tp / (tp + fp + 1e-12), 0.0)
        rec_per = np.where(tp + fn > 0, tp / (tp + fn + 1e-12), 0.0)
        f1_per = np.where(prec_per + rec_per > 0, 2 * prec_per * rec_per / (prec_per + rec_per + 1e-12), 0.0)
        precision = float(prec_per.mean())
        recall = float(rec_per.mean())
        f1 = float(f1_per.mean())
        hist['val_loss'].append(val_loss_sum / val_total)
        hist['val_acc'].append(acc)
        hist['precision'].append(precision)
        hist['recall'].append(recall)
        hist['f1'].append(f1)

        print(f'Epoch [{epoch + 1}/{EPOCHS}] '
              f'train_loss={hist["train_loss"][-1]:.4f} val_loss={hist["val_loss"][-1]:.4f} '
              f'train_acc={hist["train_acc"][-1]:.4f} val_acc={acc:.4f} '
              f'P={precision:.4f} R={recall:.4f} F1={f1:.4f}')

        if acc > best_acc:
            best_acc = acc
            patience_counter = 0
            torch.save({'state_dict': model.state_dict(), 'labels': LABELS}, 'emotion_model.pt')
            print(f'Best model saved. (Acc: {best_acc * 100:.2f}%)')
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print('Early stopping triggered!')
                break

    print(f'\nBest Validation Accuracy: {best_acc * 100:.2f}%')

    ep_idx = list(range(1, len(hist['train_loss']) + 1))
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    panels = [
        ('loss',      [('train', hist['train_loss']), ('val', hist['val_loss'])]),
        ('accuracy',  [('train', hist['train_acc']),  ('val', hist['val_acc'])]),
        ('precision', [('val', hist['precision'])]),
        ('recall',    [('val', hist['recall'])]),
        ('f1',        [('val', hist['f1'])]),
        ('lr',        [('lr', hist['lr'])]),
    ]
    for ax, (title, series) in zip(axes.flat, panels):
        for name, data in series:
            ax.plot(ep_idx, data, label=name, marker='.')
        ax.set_title(title); ax.set_xlabel('epoch'); ax.grid(True, alpha=0.3); ax.legend()
    fig.tight_layout()
    fig.savefig('results.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    main()
