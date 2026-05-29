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

### 2. Configurer et démarrer l'infrastructure IA (LLM)

RpgMaster offre une grande flexibilité et supporte plusieurs providers de modèles linguistiques (LLM) pour animer le Maître de Jeu (GM) et les compagnons IA. Vous pouvez configurer ces options soit via le fichier de configuration `.env`, soit directement à chaud depuis l'interface d'administration.

#### Option A : Ollama en Local (Recommandé pour la confidentialité et le local-first)
Ollama s'exécute directement sur votre machine. Un matériel performant (processeur graphique Apple Silicon M-Series ou GPU Nvidia RTX disposant de suffisamment de VRAM) est recommandé pour une fluidité optimale avec un modèle 7B ou 8B.

1. Téléchargez et installez **Ollama** depuis [ollama.com](https://ollama.com/).
2. Assurez-vous que l'application Ollama est lancée (ou exécutez `ollama serve` dans un terminal).
3. Téléchargez le modèle linguistique requis (par défaut `mistral:7b`) :
   ```bash
   ollama pull mistral:7b
   ```
4. Dans votre fichier `backend/.env`, assurez-vous d'avoir configuré le provider par défaut :
   ```env
   OLLAMA_BASE_URL=http://localhost:11434
   GM_MODEL=mistral:7b
   PLAYER_MODEL=mistral:7b
   ```

##### Partager Ollama sur le réseau local (ex: Ollama sur un autre ordinateur)
Si vous exécutez Ollama sur une machine dédiée performante (PC 2) de votre réseau local :
* **Sur macOS (PC 2)** : Quittez complètement l'application Ollama, puis dans un terminal exécutez :
  ```bash
  launchctl setenv OLLAMA_HOST "0.0.0.0"
  ```
  Puis relancez l'application Ollama.
* **Via terminal directement (PC 2)** :
  ```bash
  export OLLAMA_HOST=0.0.0.0
  ollama serve
  ```
* Renseignez ensuite la variable `OLLAMA_BASE_URL` dans `backend/.env` du client avec l'IP du PC 2 :
  ```env
  OLLAMA_BASE_URL=http://<IP_DU_PC_2>:11434
  ```

#### Option B : Ollama distant avec Authentification / Ollama Cloud
Si votre instance Ollama est hébergée sur un serveur distant ou protégée derrière un reverse proxy qui requiert une authentification (ex. Cloudflare Access, Nginx Basic Auth, etc.) :
* Conservez le provider par défaut `ollama`.
* Renseignez `OLLAMA_BASE_URL` avec l'URL de votre proxy.
* Configurez la clé d'API via le panneau d'administration (champ **Ollama API Key**). Le backend injectera automatiquement le header `Authorization: Bearer <clé>` dans toutes ses requêtes.

#### Option C : API compatible OpenAI (Alternative performante, sans besoin de GPU local)
Cette option permet de déléguer la génération de texte à un service externe, payant ou gratuit (comme OpenAI officiel, DeepSeek, Groq, OpenRouter, Together AI, Mistral AI Cloud, ou encore LM Studio en local).

* **Sélection du Provider** : Activez le provider `"openai_compatible"` depuis l'interface d'administration.
* **Configuration** :
  - **Base URL** : L'URL racine du service (ex: `https://api.openai.com/v1`, `https://api.deepseek.com`, `https://api.groq.com/openai/v1`, `http://localhost:1234/v1` pour LM Studio, etc.).
  - **API Key** : Votre clé API (ex: `sk-...`).
  - **Modèles** : Indiquez les modèles à cibler pour le Maître de Jeu (`GM_MODEL`) et les compagnons (`PLAYER_MODEL`) (ex: `gpt-4o`, `deepseek-chat`, `llama-3.1-70b-versatile`, etc.).

---

#### ⚙️ Configuration dynamique à chaud (Sans redémarrage)
Toutes ces configurations (changement de provider, clé API, URL, modèles) peuvent être éditées à chaud et à tout moment via le tableau de bord d'administration : **`http://localhost:5173/admin`**.

Les modifications effectuées dans l'admin sont écrites en temps réel dans le fichier de persistance `.runtime/llm_runtime.json` du backend. Elles surchargent les valeurs statiques du `.env` et survivent aux redémarrages de l'application.



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
- **Moteur LLM (Ollama ou API OpenAI-compatible)** : Fournit l'intelligence au MJ (Maître de Jeu) et aux compagnons IA, soit en local-first (Ollama), soit via des services cloud externes (OpenAI, DeepSeek, Groq, OpenRouter).

---

## 🎮 Administration
Une fois l'application démarrée, vous pouvez valider le bon fonctionnement de tous les services via le tableau de bord d'administration : rendez-vous sur **`http://localhost:5173/admin`** pour tester la santé de l'IA (LLM) et du Text-To-Speech (Kokoro-ONNX).

---

## ⚖️ Licence

Ce projet est distribué sous la licence **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

Cette licence autorise l'utilisation, la copie, la modification et la distribution du code à des fins **personnelles, éducatives, de recherche et non commerciales**. Toute exploitation commerciale, directe ou indirecte, est strictement interdite sans autorisation écrite préalable du détenteur du copyright.

