import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.memory.memory_store import store_fact, search_facts, get_all_active_facts

print("Storing test facts...")

store_fact("Sir prefers working at night.", "habit", stability="permanent", source="inferred")
store_fact("Sir is stressed about a work deadline.", "user_profile", emotional_weight="stressed", stability="temporary", source="inferred")
store_fact("Sir is building Aegon, a personal AI assistant.", "project", stability="permanent", source="explicit")

print("Facts stored.")

print("\nSearching for work-related facts...")
results = search_facts("work habits and schedule")
for r in results:
    print(f"  [{r['form']}] {r['fact']} (similarity: {r['similarity']:.3f})")

print("\nAll active facts:")
all_facts = get_all_active_facts()
for f in all_facts:
    print(f"  [{f['form']}] {f['fact']}")