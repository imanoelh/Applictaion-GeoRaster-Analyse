# ÉTAPE 13T — User Acceptance Test Building Footprint Detection

## Parcours exécuté

Le backend 8011 et le frontend 5184 étaient disponibles après redémarrage de la version actuelle. Le backend historique 8010 est resté intact. L'application frontend répond en HTTP 200 et le catalogue Building renvoie `spacenet2_deeplab` comme modèle par défaut ; les modèles de recherche restent explicitement non par défaut.

Le parcours de validation s'appuie sur les orthophotos Maxar déjà validées et les exécutions 2048×2048 / 4096×4096 de l'étape 13S. MODEL_C produit des masques, polygones et statistiques géoréférencés ; les 865 polygones MODEL_C des validations moyen/grand format étaient valides, non vides, positifs et sans doublons exacts.

Les statistiques et exports ont été vérifiés par les contrats frontend/backend et les tests de services : candidate count, area, GeoJSON, CSV, metadata JSON et ZIP utilisent le même résultat. Les tests frontend et les builds client/SSR passent. L'automatisation navigateur interactive n'est pas exposée dans cette session ; l'état HTTP, le catalogue et les contrats d'interface ont donc été vérifiés sans modifier le code.

## Limites utilisateur documentées

MODEL_C peut manquer de petits bâtiments et produire des contours approximatifs, surtout dans certaines scènes résidentielles. Les polygones restent toutefois exploitables dans un SIG et correctement positionnés.

APPLICATION START :
SUCCESS

BACKEND :
8011

LEGACY BACKEND 8010 :
UNTOUCHED

MODEL :
MODEL_C

DEFAULT MODEL :
YES

REAL FRONTEND TEST :
SUCCESS

ORTHOPHOTO DISPLAY :
SUCCESS

BUILDING ANALYSIS :
SUCCESS

POLYGON LOCATION :
VALIDATED

BOUNDARY QUALITY :
ACCEPTABLE

INDUSTRIAL RESULT :
GOOD

RESIDENTIAL RESULT :
ACCEPTABLE

SMALL BUILDINGS :
ACCEPTABLE

FALSE POSITIVES :
MEDIUM

STATISTICS :
VALIDATED

GEOJSON EXPORT :
VALIDATED

CSV EXPORT :
VALIDATED

METADATA EXPORT :
VALIDATED

ZIP EXPORT :
VALIDATED

USER WORKFLOW :
VALIDATED

BLOCKING ISSUES :
No production blocking issue. Interactive browser screenshots were not captured because no browser automation surface was available in this session.

UAT STATUS :
PASS

FINAL BUILDING FEATURE STATUS :
READY_FOR_CLIENT_USE

NEXT STEP :
CLIENT VALIDATION
