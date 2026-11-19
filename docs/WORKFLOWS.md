# Workflows frontend / backend

## Recherche d'images

1. L'utilisateur dessine une AOI.
2. Il choisit dates, capteur, resolution et nuages.
3. Le frontend construit un payload canonique.
4. Le backend lance une recherche GEE.
5. Les images ou mosaics disponibles sont retournees.
6. Le frontend affiche les cartes disponibles.

## Execution d'analyse

1. L'utilisateur choisit un index.
2. Le frontend verifie la compatibilite capteur/index.
3. Le backend cree une analyse.
4. Le backend execute un run.
5. GEE calcule l'indice ou la classification.
6. Le backend calcule statistiques, histogrammes et classes.
7. Le backend genere les URLs de tuiles.
8. Le frontend affiche la carte classifiee, la legende et les resultats.

## Change Detection

1. L'utilisateur choisit deux periodes.
2. Le backend calcule l'indice pour chaque periode.
3. Le delta est calcule:

```text
Delta = periode 2 - periode 1
```

4. Le delta est classe selon des seuils dedies.
5. La carte affiche pertes, stabilite et gains.

## OSI-SAR

1. L'utilisateur choisit OSI-SAR.
2. Le frontend force Sentinel-1 lorsque necessaire.
3. Le backend charge Sentinel-1 GRD.
4. Les signaux sombres VV/VH et le contraste local sont analyses.
5. Les classes de suspicion sont calculees.
6. Un contexte vent peut etre ajoute.
7. La carte affiche les suspects.

## Restauration depuis History

Workflow optimise:

1. L'utilisateur clique sur l'icone oeil dans History.
2. Le frontend precharge `/api/runs/{run_id}/result`.
3. Le resultat complet est stocke temporairement dans `sessionStorage`.
4. Le frontend navigue vers `/map?run_id=...`.
5. Map lit le resultat precharge.
6. Map restaure immediatement:
   - AOI;
   - index;
   - dates;
   - capteur;
   - carte classifiee;
   - legende;
   - statistiques.
7. Aucun calcul GEE ni recherche catalogue n'est relance.

