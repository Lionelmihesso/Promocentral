"""Les tests écrivent leurs fichiers (bases, flux, archives de version) dans un dossier propre à la passe, effacé à la
fin : une passe ne laisse rien dans le dossier temporaire du système (avant : ~130 dossiers et ~90 Mo par passe)."""
import atexit
import shutil
import tempfile

ROOT = tempfile.mkdtemp(prefix="promocentral-tests-")
tempfile.tempdir = ROOT
atexit.register(shutil.rmtree, ROOT, ignore_errors=True)
