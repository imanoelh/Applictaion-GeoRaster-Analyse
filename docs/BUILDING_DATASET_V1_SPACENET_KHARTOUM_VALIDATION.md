# Validation réelle SpaceNet 2 — AOI_5_Khartoum

## Statut

Validation arrêtée avant génération. Aucune extraction SpaceNet 2 / AOI_5_Khartoum
n’a été trouvée dans les répertoires locaux inspectés (`D:\Personel\TASK`,
`Downloads` et `Documents`). Aucun téléchargement automatique n’a été effectué
et aucun dataset de plusieurs dizaines de Go n’a été généré.

## Recherche effectuée

Les chemins contenant `AOI_5_Khartoum`, `Khartoum`, `SpaceNet` ou `spacenet`,
ainsi que les archives portant ces noms, ont été recherchés. Les seules
occurrences locales correspondent aux poids MODEL_C SpaceNet/DeepLab, pas aux
imagery et footprints SpaceNet 2.

## Dry-run

La commande de contrôle avec des chemins d’exemple inexistants a retourné :

```text
images_detected: 0
labels_detected: 0
pairs: 0
dry_run: true
```

Le dry-run réel AOI_5 ne peut pas être exécuté sans les deux chemins extraits.
Le script a été amélioré afin d’afficher, pour chaque paire détectée, les
dimensions, bandes, dtype, CRS, transform et le nombre de footprints après
clipping/reprojection.

## Commande à exécuter après extraction

```powershell
python backend/scripts/building_dataset/prepare_spacenet_building_dataset.py `
  --imagery <PATH_IMAGES_AOI_5_KHARTOUM> `
  --labels <PATH_LABELS_AOI_5_KHARTOUM> `
  --output <PATH_OUTPUT_EXTERNE> `
  --dry-run --limit 5
```

Après validation du résultat uniquement :

```powershell
python backend/scripts/building_dataset/prepare_spacenet_building_dataset.py `
  --imagery <PATH_IMAGES_AOI_5_KHARTOUM> `
  --labels <PATH_LABELS_AOI_5_KHARTOUM> `
  --output <PATH_OUTPUT_EXTERNE> `
  --tile-size 512 --seed 42 --limit 5
```

Puis, au maximum 20 previews :

```powershell
python backend/scripts/building_dataset/generate_dataset_preview.py `
  --dataset <PATH_OUTPUT_EXTERNE> --count 20 --seed 42
```

## Résultats actuels

- structure SpaceNet réelle : non disponible localement;
- imagery utilisée : aucune;
- labels utilisés : aucun;
- images : 0;
- labels : 0;
- paires : 0;
- tiles : 0;
- positives/négatives/rejets : non calculables;
- train/val/test : non générés;
- footprints : non calculables;
- previews : aucune;
- RAM/disque du dataset réel : non mesurés.

## Non-régression

MODEL_C8 inchangé. GEE, indices, classifications, exports, frontend, API de
production, mode offline, cache et stockage de production inchangés. Aucun
entraînement MODEL_C9 n’a été lancé.

## Décision

`WAITING_FOR_SPACENET_KHARTOUM_PATHS` — fournir l’emplacement local extrait de
SpaceNet 2 avant de relancer le dry-run. La génération complète reste bloquée
volontairement jusqu’à validation des associations et previews.
