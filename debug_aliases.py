from symptom_screener import fuzzy_match_symptom, load_symptom_tree

tree = load_symptom_tree()
print(f"Total symptoms loaded: {len(tree)}")

# Check if headache exists and has our alias
if "headache" in tree:
    aliases = tree["headache"].get("aliases", [])
    print(f"\nHeadache aliases ({len(aliases)} total):")
    if "my head is killing me" in aliases:
        print("✅ 'my head is killing me' is in aliases")
    else:
        print("❌ 'my head is killing me' NOT FOUND in aliases")
    
# Test the matching directly
result, match_type = fuzzy_match_symptom("my head is killing me", tree, threshold=0.60)
print(f"\nDirect match test: {result} (type: {match_type})")
