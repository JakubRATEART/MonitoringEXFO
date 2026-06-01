#!/usr/bin/env python3
"""
Diagnostic script to debug why extraction mapping is failing
"""
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitor_config import DESCRIPTION_TO_MODEL, DEVICES_TO_MONITOR
from utils import extract_individual_models

# Simulated extracted data from the PDF (what you showed)
pdf_extracted_data = [
    {
        "model": "High Definition Core Aligning Fusion Splicer",
        "version": "1.32",
        "release_date": "9 Jul, 2025"
    },
    {
        "model": "Core Alignment Fusion Splicer",
        "version": "1.10",
        "release_date": "18 Dec, 2025"
    },
    {
        "model": "Active Clad Alignment Fusion Splicer",
        "version": "1.16",
        "release_date": "9 Apr, 2026"
    },
    {
        "model": "Ribbon Fusion Splicer",
        "version": "1.16",
        "release_date": "3 Mar, 2026"
    },
    {
        "model": "Handheld Fusion Splicer",
        "version": "1.08",
        "release_date": "20 Jul, 2020"
    }
]

print("=" * 80)
print("DIAGNOSTIC: Testing Extraction Mapping")
print("=" * 80)

print("\n1. DESCRIPTION_TO_MODEL mapping:")
for desc, device in DESCRIPTION_TO_MODEL.items():
    print(f"   '{desc}' -> '{device}'")

print("\n2. PDF extracted descriptions:")
for item in pdf_extracted_data:
    print(f"   '{item['model']}'")

print("\n3. Testing matching logic:")
for item in pdf_extracted_data:
    model_string = item['model']
    print(f"\n   Checking: '{model_string}'")

    for description, device_model in DESCRIPTION_TO_MODEL.items():
        desc_lower = description.lower()
        model_lower = model_string.lower()

        # Test the matching condition
        match1 = desc_lower in model_lower
        match2 = model_lower in desc_lower
        matches = match1 or match2

        print(f"      vs '{description}':")
        print(f"         desc in model: {match1}")
        print(f"         model in desc: {match2}")
        print(f"         -> {'MATCH' if matches else 'no match'}")

        if matches:
            break

print("\n4. Running extract_individual_models():")
result = extract_individual_models(pdf_extracted_data, DEVICES_TO_MONITOR)

if result:
    print(f"\n   SUCCESS: Got {len(result)} individual models")
    for item in result:
        print(f"      - {item['model']}: v{item['version']} ({item['source_string']})")
else:
    print(f"\n   FAILED: Got empty list!")
    print("      This is the bug - mapping is not working")

print("\n" + "=" * 80)
