"""Écriture de fichiers JSON sans risque de fichier tronqué en cas de coupure."""
import json
import os
import tempfile


def ecrire_json_atomique(path, data):
    """Écrit dans un fichier temporaire du même dossier, puis le substitue d'un coup."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as file:
            temporary = file.name
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
