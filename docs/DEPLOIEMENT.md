# Déploiement (Oracle Cloud Always Free, VM partagée avec rag-LexEU)

La VM ARM (A1.Flex 4 OCPU / 24 Go, Ubuntu 24.04) héberge déjà rag-LexEU. Cette démo s'y ajoute :

- son propre stack Compose dans `/opt/sinistre` (app + Postgres/pgvector, ~2 Go au maximum) ;
- attaché au réseau Docker `lexeu_default`, pour que **le Caddy de LexEU** serve le sous-domaine et que **son serveur BGE-M3** calcule les embeddings ;
- URL : `https://sinistre.51-170-130-195.sslip.io` (sslip.io résout tout sous-domaine vers l'IP ; Caddy obtient le certificat).

Les ports 80/443 sont déjà ouverts (Security List du VCN **et** iptables de l'image Ubuntu Oracle) pour LexEU : rien à faire.

## 1. Côté LexEU (une fois)

Le Caddyfile de LexEU contient un bloc `{$SINISTRE_DOMAIN}` qui proxifie vers `sinistre:8000`. Sur la VM :

```bash
cd /opt/lexeu && echo 'SINISTRE_DOMAIN=sinistre.51-170-130-195.sslip.io' >> .env
```

Puis redéployer LexEU (push sur `main`, ou `docker compose -f compose.prod.yml up -d caddy`).

## 2. Le stack de la démo

```bash
sudo mkdir -p /opt/sinistre/data/raw && sudo chown -R deploy:deploy /opt/sinistre
sudo chown -R 1000:1000 /opt/sinistre/data   # l'app tourne en uid 1000 dans le conteneur
cd /opt/sinistre
# copier deploy/docker-compose.prod.yml ici, puis créer .env :
cat > .env <<'EOF'
SINISTRE_TAG=latest
POSTGRES_PASSWORD=<openssl rand -hex 24>
GEMINI_API_KEY=<clé Google AI Studio>
MAX_ANALYSES_PAR_JOUR=300
EOF
chmod 600 .env
docker compose -f docker-compose.prod.yml up -d --wait
```

## 3. Données

Les PDF ne sont jamais dans le dépôt : ils sont téléchargés depuis leur source. La base structurée (extraction LLM payée une seule fois) est construite en local puis restaurée :

```bash
# en local
make dump                                   # -> data/sinistre.dump
scp data/sinistre.dump ubuntu@51.170.130.195:/tmp/
# sur la VM
docker compose -f docker-compose.prod.yml exec app python -m scripts.fetch_corpus
docker compose -f docker-compose.prod.yml exec -T postgres pg_restore -U sinistre -d sinistre --clean --if-exists < /tmp/sinistre.dump
docker compose -f docker-compose.prod.yml restart app   # pré-calcule les exemples
```

Alternative sans dump : `docker compose ... exec app python -m scripts.ingest` (appels LLM, ~15 min).

## 4. Déploiement continu (optionnel)

La CI construit l'image arm64 (`ghcr.io/zakariae92/sinistre-cg`) à chaque push sur `main`. Le job « Deploy » s'active quand le dépôt a :
variables `VM_HOST`, `VM_SSH_KNOWN_HOSTS`, `SINISTRE_DOMAIN` et secret `VM_SSH_KEY` (la même clé `deploy` que LexEU).

## 5. Garde-fous

- `restart: unless-stopped`, healthcheck `/health`, limites mémoire (1 Go app, 1 Go Postgres).
- 10 analyses par IP et par heure, plafond quotidien `MAX_ANALYSES_PAR_JOUR` ; les exemples et analyses déjà en cache ne comptent pas.
- Alerte budgétaire OCI à 1 € et plafond de dépense côté Google AI Studio.
