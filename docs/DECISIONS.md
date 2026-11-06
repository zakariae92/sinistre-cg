# Décisions

| # | Décision | Pourquoi |
|---|---|---|
| 1 | LLM : Gemini (`gemini-3.8-flash` pour l'analyse, `gemini-3.5-flash` en réflexion « low » pour l'extraction), derrière l'interface `LLMClient` | Clé disponible ; structured output natif à partir des schémas Pydantic. Changer de fournisseur = une nouvelle classe. |
| 2 | Embeddings BGE-M3 servis localement (TEI en local, serveur ONNX de rag-LexEU en production) | Multilingue FR/EN, aucun appel externe pour la recherche, et zéro RAM en plus sur la VM : le serveur de LexEU est réutilisé. |
| 3 | Postgres 17 + pgvector, FTS `french`, schéma SQL idempotent (`schema.sql`) au démarrage | Une seule base pour le structuré, le plein texte et les vecteurs ; pas d'outil de migration pour un schéma aussi petit. |
| 4 | Corpus : AXA OptiHome en **français** (la version FR existe), Allianz et MAPA retirés (404), Altima ajouté | 6 contrats vérifiés sur 3 pays. Aucun contrat Foyer (employeur visé). |
| 5 | Contrôle « CG complètes » sur des racines (`exclu`, `défini`, `lexique`) | Baloise écrit « exclus » et « notions » : le contrôle sur les mots entiers rejetait des CG complètes. |
| 6 | Parsing générique : titres = police plus grande que le corps, ou ligne courte en gras ; numéros seuls fusionnés avec le titre suivant ; en-têtes/pieds = texte répété dans les marges ; pages de sommaire ignorées | Fonctionne sur les 6 mises en page sans règle par assureur. Les fils d'Ariane restent imparfaits sur les mises en page en colonnes (limite assumée). |
| 7 | Pas d'extraction heuristique séparée des définitions | L'extraction LLM validée couvre les lexiques ; une seconde source à fusionner n'apportait pas assez pour son code. |
| 8 | Un seul cache Postgres (`cache`) pour les qualifications et les analyses, clé = hash(entrées, `PROMPT_VERSION`) | Les exemples sont calculés une fois puis servis instantanément, même après redémarrage. |
| 9 | Rate limit en mémoire (10/h/IP, plafond quotidien) plutôt que slowapi | Quelques lignes, un seul worker. Les analyses en cache ne comptent pas. |
| 10 | Évaluation sur le contrat luxembourgeois uniquement | Budget d'appels LLM du niveau gratuit ; `make eval CONTRAT=...` pour les autres. |
| 11 | Déploiement sur la VM de rag-LexEU : réseau Docker partagé, bloc ajouté dans le Caddyfile de LexEU, sous-domaine sslip.io | Un seul Caddy et un seul certificat ACME par domaine ; la VM a la place (4 OCPU / 24 Go). |
| 12 | La base est construite en local puis restaurée sur la VM (`pg_dump`) ; les PDF sont re-téléchargés sur la VM | L'extraction LLM n'est payée qu'une fois ; rien de dérivé des PDF n'est versionné. |
