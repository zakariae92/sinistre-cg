# Rapport d'évaluation (axa-lu-optihome, 2026-11-06, gemini-3.8-flash)

- **exactitude** : 68
- **exactitude_validee** : None
- **fidelite** : 100
- **rappel_clauses** : None
- **detection_ambiguites** : 40
- **latence** : 57 s / 89 s

| cas | attendu | obtenu | ok | citations ✓/✗ | note |
|---|---|---|---|---|---|
| velo-local-commun-sans-precision | AMBIGU/INFORMATION_MANQUANTE (proposé) | INFORMATION_MANQUANTE | ✅ | 6/0 | dépend de la fermeture du local et de l'effraction |
| velo-local-commun-non-ferme | NON_COUVERT (proposé) | NON_COUVERT | ✅ | 6/0 | vol sans effraction dans un local non fermé |
| velo-local-commun-effraction | COUVERT/AMBIGU (proposé) | NON_COUVERT | ❌ | 6/0 | obtenu NON_COUVERT, attendu COUVERT|AMBIGU. effraction d'un local commun fermé |
| bougie-week-end | AMBIGU/COUVERT (proposé) | COUVERT | ✅ | 6/0 | mobilier de jardin et incendie : vérifier les biens extérieurs assurés |
| bougie-trois-semaines | AMBIGU/NON_COUVERT (proposé) | COUVERT | ❌ | 6/0 | obtenu COUVERT, attendu AMBIGU|NON_COUVERT. inoccupation prolongée + bien extérieur |
| bougie-table-interieur | COUVERT (proposé) | COUVERT | ✅ | 6/0 | incendie à l'intérieur du logement |
| vol-effraction-porte | COUVERT (proposé) | INFORMATION_MANQUANTE | ❌ | 6/0 | obtenu INFORMATION_MANQUANTE, attendu COUVERT. vol avec effraction du logement |
| vol-porte-ouverte | NON_COUVERT/AMBIGU (proposé) | NON_COUVERT | ✅ | 5/0 | vol sans effraction ni violence |
| vol-cave-privative | COUVERT/AMBIGU (proposé) | NON_COUVERT | ❌ | 7/0 | obtenu NON_COUVERT, attendu COUVERT|AMBIGU. dépendance : souvent plafond spécifique |
| vol-voiture | NON_COUVERT (proposé) | INFORMATION_MANQUANTE | ❌ | 6/0 | obtenu INFORMATION_MANQUANTE, attendu NON_COUVERT. hors de l'habitation assurée |
| ddE-machine-a-laver | COUVERT (proposé) | COUVERT | ✅ | 7/0 | fuite accidentelle d'un appareil |
| ddE-gel-inoccupe | NON_COUVERT/AMBIGU (proposé) | INFORMATION_MANQUANTE | ❌ | 6/0 | obtenu INFORMATION_MANQUANTE, attendu NON_COUVERT|AMBIGU. mesures de prévention du gel non respectées |
| ddE-toiture | COUVERT/AMBIGU (proposé) | COUVERT | ✅ | 6/0 | infiltration par toiture : selon entretien |
| ddE-humidite | NON_COUVERT (proposé) | NON_COUVERT | ✅ | 6/0 | dommage progressif, souvent exclu |
| incendie-friteuse | COUVERT (proposé) | COUVERT | ✅ | 6/0 |  |
| incendie-court-circuit | COUVERT/AMBIGU (proposé) | COUVERT | ✅ | 7/0 | dommages électriques : garantie parfois optionnelle |
| bris-vitre-ballon | COUVERT/AMBIGU (proposé) | COUVERT | ✅ | 7/0 | bris de glace : parfois optionnel |
| bris-ecran-tv | NON_COUVERT/AMBIGU (proposé) | COUVERT | ❌ | 6/0 | obtenu COUVERT, attendu NON_COUVERT|AMBIGU. écrans souvent exclus du bris de glace |
| rc-enfant-vitre-voisin | COUVERT (proposé) | COUVERT | ✅ | 6/0 | RC vie privée |
| rc-chien-morsure | COUVERT/AMBIGU (proposé) | COUVERT | ✅ | 6/0 | RC animaux ; chiens dangereux parfois exclus |
| tempete-arbre-toiture | COUVERT (proposé) | COUVERT | ✅ | 6/0 |  |
| tempete-mobilier-jardin | AMBIGU/NON_COUVERT (proposé) | COUVERT | ❌ | 7/0 | obtenu COUVERT, attendu AMBIGU|NON_COUVERT. mobilier extérieur souvent exclu ou plafonné |
| piege-intentionnel | NON_COUVERT (proposé) | NON_COUVERT | ✅ | 6/0 | faute intentionnelle |
| piege-usure | NON_COUVERT (proposé) | NON_COUVERT | ✅ | 6/0 | usure |
| piege-vague | INFORMATION_MANQUANTE/AMBIGU (proposé) | INFORMATION_MANQUANTE | ✅ | 6/0 | doit déclencher des questions |
