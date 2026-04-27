from kokoro import KPipeline
import soundfile as sf
import time

print("Initialisation de Kokoro TTS (téléchargement des poids ~300 Mo si c'est la première fois)...")
# Initialiser le pipeline pour le français (lang_code='f')
pipeline = KPipeline(lang_code='f') 

texte = "Salutations, aventurier ! Je suis Kokoro, votre nouveau narrateur pour RpgMaster. Est-ce que le son de ma voix vous convient ?"

print(f"Génération de l'audio avec le texte : '{texte}'")
start_time = time.time()

# Génération de la voix (ff_siwis est la voix féminine française standard de Kokoro)
generateur = pipeline(texte, voice='ff_siwis', speed=1.0)

# Le générateur peut découper les phrases longues, on boucle sur les morceaux
for index, (graphemes, phonemes, audio) in enumerate(generateur):
    nom_fichier = f"voix_rpg_test_{index}.wav"
    # Sauvegarde à 24000 Hz (fréquence native de Kokoro)
    sf.write(nom_fichier, audio, 24000)
    print(f"Succès ! Fichier sauvegardé sous le nom : {nom_fichier}")

print(f"Temps de génération total : {time.time() - start_time:.2f} secondes.")
