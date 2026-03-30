from kokoro_onnx import Kokoro
import soundfile as sf
import os
import urllib.request

print("Démarrage du test ONNX Kokoro TTS pour RpgMaster")

# Téléchargement automatique des modèles v1.0 si absents
# Ces modèles utilisent le format ONNX, ultra optimisé pour la puce M4
if not os.path.exists("kokoro-v1.0.onnx"):
    print("Téléchargement du modèle ONNX (une seule fois)...")
    urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx", "kokoro-v1.0.onnx")

if not os.path.exists("voices-v1.0.bin"):
    print("Téléchargement des voix (une seule fois)...")
    urllib.request.urlretrieve("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin", "voices-v1.0.bin")

try:
    print("Chargement du modèle dans la mémoire du M4...")
    kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
    
    texte = "Salutations, aventurier ! Que les dieux de la taverne veillent sur vos dés critiques. Comment puis-je vous aider ?"
    print(f"Génération de la voix française... ({texte})")
    
    # Lang='fr-fr' garantit une parfaite compréhension de la phonétique française
    samples, sample_rate = kokoro.create(
        texte, 
        voice="ff_siwis", 
        speed=1.0, 
        lang="fr-fr"
    )
    
    output = "voix_onnx.wav"
    sf.write(output, samples, sample_rate)
    print(f"Succès total ! Fichier sauvegardé vers {output} (Durée: {len(samples)/sample_rate:.2f} secondes)")

except Exception as e:
    print("Erreur pendant la génération:", e)
