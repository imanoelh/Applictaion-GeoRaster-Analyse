# Étape 12 — Clôture technique et protocole de validation terrain

## Nature de cette étape

Cette étape consolide l’état livré et prépare la reprise dès que les données terrain seront disponibles. Elle ne constitue pas une validation scientifique supplémentaire et n’invente aucune réalisation absente du projet.

## État de clôture

Le pipeline logiciel est complet de la source jusqu’au frontend et aux exports :

```text
GeoTIFF → validation → tuiles → modèle réel → probabilités
→ masque global → polygones → résultat → carte → exports
```

Les responsabilités sont séparées, les contrats sont versionnés, le géoréférencement est conservé et les analyses historiques restent intactes. Le système peut être démontré avec Sentinel-2 comme test d’intégration ou recevoir une orthophoto locale conforme.

## Protocole de reprise terrain

Après l’audit réel 2024–2025, l’ordre de validation restant est :

1. définir un profil d’ingestion approuvé pour les COG Maxar Multi-8 UInt16 ;
2. importer exclusivement via l’interface et `POST /api/ai/raster/local` ;
3. exécuter le baseline avec seuil 0,50 et paramètres actuels ;
4. vérifier visuellement les contours et l’alignement spatial ;
5. aligner et rasteriser la vérité terrain dans un CRS projeté commun ;
6. calculer TP, FP, FN, TN, précision, rappel, F1 et IoU pixel ;
7. appliquer un matching objet déterministe 1-à-1 et documenter fusions/splits ;
8. calibrer une seule famille de paramètres à la fois : seuil, taille minimale, trous, morphologie ;
9. versionner une configuration uniquement si l’amélioration est mesurée ;
10. rejouer tous les tests et builds.

## Critères de passage

La précision scientifique ne pourra passer à `VALIDATED` qu’avec un jeu de référence traçable et des métriques reproductibles. Une calibration devra indiquer la plage de GSD couverte : des paramètres validés à 0,20 m/pixel ne doivent pas être appliqués aveuglément à 1 m/pixel.

## Statut final honnête

- pipeline et modèle réel : prêts ;
- frontend et exports : prêts ;
- orthophoto réelle : disponible, COG originaux non directement compatibles ;
- vérité terrain : non disponible ;
- calibration : non disponible ;
- exactitude scientifique : non validée.

**Statut : clôture technique documentée ; validation terrain à exécuter lorsque les données seront fournies.**

