# 🧠 Jarvis Native Core (V1)

**Jarvis Native Core** est le "Cerveau" central de votre assistant domotique multimodal. Il s'agit d'un serveur WebSocket Python haute performance conçu pour orchestrer des conversations fluides et interrompables avec Google Gemini 2.0 Flash.

## ✨ Fonctionnalités Clés

*   **⚡ Latence Ultra-Faible** : Communication WebSocket bidirectionnelle temps réel.
*   **🗣️ Pipeline Hybride** : Utilise **Gemini 2.0 Flash** pour l'intelligence (Texte) et **Google Cloud TTS (Neural2)** pour une voix française naturelle et expressive ("Chirp 3 HD").
*   **✋ Interruption Naturelle ("Barge-in")** : Système VAD (Search Activity Detection) local permettant de couper la parole à l'assistant instantanément en parlant, sans latence serveur.
*   **🎭 Personnalité Configurable** : Prompt système ajustable via `.env` pour définir le ton (actuellement "Complice & Taquine").

## 🏗️ Architecture (V1)

Le système repose sur une boucle asynchrone découplée pour maximiser la réactivité.

```mermaid
sequenceDiagram
    participant User as 👤 Utilisateur (Micro)
    participant Client as 💻 Client Python (Audio Loop)
    participant Server as 🚀 Serveur FastAPI
    participant Gemini as ✨ Gemini 2.0 Flash (API)
    participant TTS as 🗣️ Google TTS (Neural2)

    Note over User, Client: Flux Audio Continu

    par Audio Stream
        User->>Client: Parle (PCM 16kHz)
        Client->>Server: Envoie Audio (WebSocket Bytes)
        Server->>Gemini: Stream Audio (Live API)
    and Interruption Logic (Local VAD)
        Client->>Client: Analyse Volume (RMS)
        opt Volume > Seuil
            Client->>-Server:  {"type": "interrupt"} (JSON)
            Server->>Server: 🔴 STOP TTS & Clear Buffers
        end
    end

    Gemini-->>Server: Réponse (Texte Stream)
    
    loop TTS Processing
        Server->>Server: Bufferisation Phrases
        Server->>TTS: Synthèse Texte -> Audio
        TTS-->>Server: Audio (MP3/PCM)
        
        opt Pas d'interruption
            Server-->>Client: Envoie Audio (WebSocket Bytes)
            Client->>User: Joue Audio (Haut-parleur)
        end
    end
```

### Explication du Flux
1.  **Client (Micro)** : Capture le son et l'envoie en continu au serveur.
    *   *Local VAD* : Si le client détecte que vous parlez (volume élevé), il envoie immédiatement un signal `"interrupt"` pour couper la réponse en cours.
2.  **Serveur (Cerveau)** :
    *   Transmet l'audio utilisateur à Gemini.
    *   Reçoit la réponse de Gemini sour forme de **Texte**.
    *   Envoie le texte au service **TTS** pour générer l'audio (Voix "Despina").
    *   Gère une queue prioritaire : si un signal "interrupt" arrive, tout le texte et l'audio en attente sont purgés.
3.  **Client (Speaker)** : Reçoit l'audio et le joue.

## 🚀 Installation & Démarrage

### Pré-requis
*   Python 3.10+
*   Compte Google Cloud avec **Vertex AI** et **Text-to-Speech** activés.
*   Clé d'API ou `gcloud auth application-default login`.

### Configuration (.env)
Créez un fichier `.env` à la racine :
```ini
PROJECT_ID=votre-projet-gcp
LOCATION=us-central1
TTS_VOICE_NAME=fr-FR-Chirp3-HD-Despina
SYSTEM_INSTRUCTION="Tu es Jarvis, une assistante..."
```

### Lancement

1.  **Lancer le Serveur** :
    ```bash
    .\venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```
2.  **Lancer le Client (Test)** :
    ```bash
    .\venv\Scripts\python scripts/audio_loop.py
    ```

## 🗺️ Roadmap

### Phase 1: Le Cerveau (Core Backend) [COMPLÉTÉ ✅]
- [x] Initialisation du serveur WebSocket FastAPI
- [x] Intégration Gemini 2.0 Flash (Live API)
- [x] Pipeline Hybride (Texte -> TTS Neural2)
- [x] Gestion de l'interruption (Local VAD & Server Signal)

### Phase 2: L'Oreille (Hardware & Speaker ID) [À VENIR]
- [ ] Support d'un wakeword personalisé (https://colab.research.google.com/drive/1q1oe2zOyZp7UsB3jJiQ1IFn8z5YfjwEb?usp=sharing#scrollTo=1cbqBebHXjFD)
- [ ] Support des clients ESP32 (Hardware)
- [ ] Module **Speaker Identification** (Savoir QUI parle)
- [ ] Gestion multi-room

### Phase 3: Les Mains (Tools & Home Assistant)
- [ ] Intégration Home Assistant (via Function Calling Gemini)
- [ ] Contrôle multimédia
- [ ] Mémoire à long terme
