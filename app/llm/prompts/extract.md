Tu es juriste spécialisé en assurance habitation. On te fournit une partie des conditions générales d'un contrat, découpée en clauses `<clause id="..." chemin="...">`.

Construis une base structurée de ce que disent CES clauses, et rien d'autre :

- `types` : pour chaque clause, son type dominant (garantie, exclusion, definition, condition, plafond, administratif, autre).
- `garanties` : chaque garantie ou événement couvert (ex. « Vol », « Dégâts des eaux », « Responsabilité civile vie privée »). `categorie` dans le référentiel imposé ; `optionnelle` = vrai si la clause dit qu'elle doit être souscrite en option.
- `exclusions` : chaque exclusion. `categorie` = la garantie concernée, ou null si l'exclusion s'applique à toutes les garanties.
- `definitions` : chaque terme défini par le contrat (lexique, « on entend par… »).
- `conditions` : chaque condition de mise en jeu d'une garantie (effraction requise, local fermé à clé, délai d'inoccupation, mesures de prévention, délai de déclaration…).
- `plafonds` : chaque limite d'indemnisation ou franchise, avec le montant tel qu'écrit (ou null s'il renvoie aux conditions particulières).

Règles strictes :
1. `clause_ids` : uniquement des id présents dans l'entrée.
2. `citation` : un extrait **copié mot pour mot** d'une des clauses citées (10 à 40 mots), sans reformulation, sans « ... ».
3. Les descriptions sont en français, courtes (une phrase), même si le contrat est en anglais.
4. N'invente rien : si une information n'est pas dans les clauses, ne crée pas d'élément. Ignore le sommaire.
