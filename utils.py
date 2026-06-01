from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def extract_individual_models(grouped_versions_list: List[Dict], devices_to_monitor: Dict[str, List[str]]):
    """
    Parse extracted model codes and match them to monitored devices.
    Simply matches extracted model codes to device variants.
    """
    print(f"[UTILS] extract_individual_models called with {len(grouped_versions_list)} items", flush=True)
    logger.info(f"[UTILS] extract_individual_models called with {len(grouped_versions_list)} items")

    individual_models = []

    if not grouped_versions_list:
        logger.warning("[UTILS] grouped_versions_list is empty")
        return individual_models

    if not devices_to_monitor:
        logger.error("[UTILS] devices_to_monitor is empty!")
        return individual_models

    logger.info(f"[UTILS] Processing {len(grouped_versions_list)} items")

    for idx, item in enumerate(grouped_versions_list):
        model_code = item.get('model', '').strip()
        version = item.get('version')
        release_date = item.get('release_date')

        logger.info(f"[UTILS] ═══════════════════════════════════════════════════════════")
        logger.info(f"[UTILS] Processing Item #{idx}: '{model_code}' v{version}")

        if not version:
            logger.warning(f"[UTILS] ❌ Skipping item {idx} - NO VERSION found")
            continue

        if not model_code:
            logger.warning(f"[UTILS] ❌ Skipping item {idx} - NO MODEL CODE found")
            continue

        # Direct lookup: check if model_code matches any device or variant
        matched_device = None
        matched_variant = None

        # First, check if the model code is directly a device name
        if model_code in devices_to_monitor:
            matched_device = model_code
            matched_variant = model_code
            logger.info(f"[UTILS] ✅ DIRECT MATCH: '{model_code}' is a known device")
        else:
            # Check if model_code matches any variant (case-insensitive, partial match)
            model_code_lower = model_code.lower()
            for device_name, variants in devices_to_monitor.items():
                for variant in variants:
                    variant_lower = variant.lower()
                    # Check for partial match (e.g., "T-72C+" matches "TYPE-72C+")
                    if variant_lower in model_code_lower or model_code_lower in variant_lower:
                        matched_device = device_name
                        matched_variant = variant
                        logger.info(f"[UTILS] ✅ VARIANT MATCH: '{model_code}' matches variant '{variant}' of device '{device_name}'")
                        break
                if matched_device:
                    break

        if matched_device:
            individual_models.append({
                'model': matched_device,
                'variant': matched_variant,
                'version': version,
                'release_date': release_date,
                'source_string': model_code
            })
            print(f"[UTILS] ✅ Added to DB: {matched_device} v{version}", flush=True)
            logger.info(f"[UTILS] ✅ INSERTED: {matched_device} v{version}")
        else:
            logger.warning(f"[UTILS] ⚠️  NO MATCH for '{model_code}' - skipping")

    print(f"[UTILS] FINAL: Returning {len(individual_models)} models (from {len(grouped_versions_list)} input items)", flush=True)
    logger.info(f"[UTILS] ═══════════════════════════════════════════════════════════")
    logger.info(f"[UTILS] FINAL: Total extracted models: {len(individual_models)}")
    logger.info(f"[UTILS] Models to be inserted: {[m['model'] + ' v' + m['version'] for m in individual_models]}")
    return individual_models
