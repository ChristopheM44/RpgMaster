# RpgMaster

RpgMaster est une plateforme de jeu de rôle (JDR) augmentée par l'Intelligence Artificielle. Elle combine un moteur de règles complet basé sur le SRD 5.2 (D&D), une narration dynamique propulsée par un LLM (Mistral 7B via Ollama), et une génération vocale (TTS) avec Kokoro-ONNX.

Ce guide détaille les étapes pour déployer le projet sur une nouvelle machine (serveur local ou distant, idéalement avec un hardware imposant pour faire tourner les modèles locaux fluidement).

---

## 📋 Prérequis matériels et logiciels

1. **Hardware recommandé :** CPU/GPU performant pour l'exécution d'Ollama (Apple Silicon M-Series, Nvidia RTX avec suffisamment de VRAM pour héberger un modèle 7B/8B).
2. **Ollama** installé nativement sur votre machine (disponible sur [ollama.com](https://ollama.com/)).
3. **Python 3.9+** (pour le backend FastAPI).
4. **Python 3.11** (strictement requis pour le micro-service TTS `kokoro-onnx`).
5. **Node.js 18+ & npm** (pour le frontend Vue 3).
6. **Git** (pour récupérer le code).

---

## 🚀 Guide d'installation étape par étape

### 1. Cloner le projet
Puisque le projet est sur Git, commencez par le cloner sur la nouvelle machine :
```bash
git clone <URL_DE_VOTRE_DEPOT_RPGMaster>
cd RpgMaster
```

### 2. Démarrer l'infrastructure IA (Ollama)
Ollama sert de moteur pour le Maître du Jeu et les joueurs IA.

Assurez-vous que l'application Ollama est lancée sur votre Mac (ou exécutez `ollama serve` dans un terminal).
Puis, téléchargez le modèle linguistique requis (par défaut `mistral:7b`) :
```bash
ollama pull mistral:7b
```
*Note : Ollama tourne par défaut sur le port local `11434`.*

#### Utiliser Ollama depuis un autre Mac sur le même réseau

Si Ollama tourne sur un Mac différent (Mac 2) et que vous souhaitez l'exposer sur le réseau local :

1. Fermez complètement l'application Ollama sur le Mac 2 (vérifiez aussi l'icône dans la barre des menus en haut à droite).

2. Ouvrez un Terminal sur le Mac 2 et exécutez la commande suivante pour que Ollama écoute sur toutes les interfaces réseau :
   ```bash
   launchctl setenv OLLAMA_HOST "0.0.0.0"
   ```

3. Relancez l'application Ollama.

> **Alternative via terminal :** Si vous préférez démarrer Ollama directement en ligne de commande sans passer par l'application :
> ```bash
> export OLLAMA_HOST=0.0.0.0
> ollama serve
> ```

Une fois Ollama accessible sur le réseau, mettez à jour la variable `OLLAMA_BASE_URL` dans `backend/.env` avec l'adresse IP du Mac 2 :
```
OLLAMA_BASE_URL=http://<IP_DU_MAC_2>:11434
```

### 3. Configurer le micro-service TTS restreint (Kokoro-ONNX)
Le système vocal (Text-to-Speech) fonctionne en micro-service isolé car il cible Python 3.11 spécifiquement pour des questions de compatibilité.
```bash
cd tts_service
# Créer un environnement virtuel en Python 3.11 obligatoirement
python3.11 -m venv .venv
source .venv/bin/activate

# Installer les dépendances du TTS
pip install -r requirements.txt
# (Note : les modèles ONNX et voix se téléchargeront automatiquement à la première exécution)

# Revenir à la racine
deactivate
cd ..
```

### 4. Configurer le Backend (FastAPI / Moteur de règles)
Le backend contient le moteur de jeu, l'API REST, et la gestion des WebSockets.
```bash
cd backend

# Créer un environnement virtuel (Python 3.9+)
python -m venv .venv
source .venv/bin/activate

# Installer les dépendances via pyproject.toml ou requirements.txt 
pip install -e .

# Configurer les variables d'environnement
cp ../.env.example .env

# Créer la base de données (obligatoire à la première installation)
alembic upgrade head
```
*(Optionnel) Éditez le fichier `.env` si vous devez modifier les ports, l'hôte (`APP_HOST`) ou le modèle LLM.*

Pour lancer le backend :
```bash
# Pour le développement
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Pour la production
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```
*L'API sera disponible sur `http://localhost:8000`.*

### 5. Configurer le Frontend (Vue 3 / TypeScript)
Le frontend est une application moderne utilisant Pinia et TailwindCSS.
```bash
# Dans un nouveau terminal
cd frontend
npm install

# Option A : Pour développer / tester
npm run dev
# L'interface sera disponible sur http://localhost:5173

# Option B : Pour un déploiement de production (Serveur Web)
npm run build
# Les fichiers générés dans le dossier `dist/` pourront être servis par Nginx, Apache, ou un CDN.
```

---

## 🏗️ Architecture des services en exécution complète

Une fois tout déployé, voici comment les différents services interagissent :

- **VueJS Frontend** (`:5173` ou `:80`) : Interface utilisateur (WebSockets & REST).
- **FastAPI Backend** (`:8000`) : Chef d'orchestre, Engine D&D, DB SQLite `rpgmaster.db`.
- **Micro-service TTS** (`Subprocess` par Backend) : Activé par le backend lors d'un event "Narration" avec isolation de Python.
- **Ollama Local** (`:11434`) : Fournit l'intelligence au MJ (Maître de Jeu) et PNJ en local-first.

---

## 🎮 Administration
Une fois l'application démarrée, vous pouvez valider le bon fonctionnement de tous les services via le tableau de bord d'administration : rendez-vous sur **`http://localhost:5173/admin`** pour tester la santé de l'IA (LLM) et du Text-To-Speech (Kokoro-ONNX).
