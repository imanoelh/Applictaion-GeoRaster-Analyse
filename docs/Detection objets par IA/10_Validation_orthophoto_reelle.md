# Étape 10 — Validation sur orthophoto réelle

Deux orthophotos Maxar réelles sont désormais disponibles et ont été auditées. Les COG originaux sont valides mais non directement compatibles avec `LocalRasterSource` : huit bandes UInt16, taille supérieure à 512 Mio et nombre de pixels supérieur à la limite du post-traitement.

Deux sous-zones RGB uint8 alignées et entièrement traçables ont néanmoins permis de valider techniquement le modèle réel, les résultats, l’alignement et les exports pour 2024 et 2025. Aucune vérité terrain n’est disponible et l’exactitude scientifique demeure non validée.

Le rapport complet et les métriques se trouvent dans :

[Validation réelle 2024–2025](10B_Validation_reelle_orthophotos_2024_2025.md)

**Statut : partiellement validée.**

