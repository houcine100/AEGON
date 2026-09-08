# resave_model.py — run ONCE, then you can delete it.
from pathlib import Path
from sentence_transformers import SentenceTransformer

target = Path(r"C:\Users\houci\Desktop\aegon\core\memory\embedding_model")
model = SentenceTransformer("all-MiniLM-L6-v2")
model.save(str(target))
print("Saved a clean copy to:", target)