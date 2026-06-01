# Shared configuration for monitored devices

DEVICES_TO_MONITOR = {
    'T-72C+': ['TYPE-72C+', 'Q102-CA+', 'TYPE-82C+'],
    'T-57C+': ['T-57C+', 'T-56+', 'T-601C+', 'T-601CS+'],
    'T-502S': ['T-502S', 'Q502S'],
    'T-402S': ['T-402S', '51V/51V Ultra'],
    'T-400S': ['T-400S'],  # If found in PDF
    'T-72M12+': ['TYPE-72M12+', 'Q102M12+']
}

# Map PDF descriptions to device models
# This helps match extracted descriptions to actual device models
DESCRIPTION_TO_MODEL = {
    'High Definition Core Aligning Fusion Splicer': 'T-72C+',
    'Core Alignment Fusion Splicer': 'T-57C+',
    'Active Clad Alignment Fusion Splicer': 'T-502S',
    'Ribbon Fusion Splicer': 'T-72M12+',
    'Handheld Fusion Splicer': 'T-400S',
}

# Legacy mapping for backward compatibility with web_monitor
# Includes both EXFO and Sumitomo devices
MONITORED_MAP = {
    # EXFO devices (original)
    'FastReporter 3': 'https://apps.exfo.com/en/exfo-apps/?platform=PC&platformCategory=PC%20Software',
    'ConnectorMax 2': 'https://apps.exfo.com/en/exfo-apps/?platform=PC&platformCategory=PC%20Software',
    'LXM': 'https://apps.exfo.com/en/exfo-apps/?platform=LXM&platformCategory=Handheld+Units',
    'AXS-1xx': 'https://apps.exfo.com/en/exfo-apps/?platform=AXS-1XX&platformCategory=Handheld+Units',
    'MAX-Optical System Image': 'https://apps.exfo.com/en/exfo-apps/?platform=MAX-700C/D&platformCategory=Handheld+Units',
    'PXM': 'https://apps.exfo.com/en/exfo-apps/?platform=PXM&platformCategory=Handheld+Units',
    'EXFO Exchange': 'https://apps.exfo.com/en/exfo-apps/software/exchange',
    # Sumitomo devices (new)
    'T-72C+': 'https://global-sei.com/sumitomo-electric-splicers/emea/common/img/support/firmware_update/Latest%20software%20version.pdf',
    'T-57C+': 'https://global-sei.com/sumitomo-electric-splicers/emea/common/img/support/firmware_update/Latest%20software%20version.pdf',
    'T-502S': 'https://global-sei.com/sumitomo-electric-splicers/emea/common/img/support/firmware_update/Latest%20software%20version.pdf',
    'T-402S': 'https://global-sei.com/sumitomo-electric-splicers/emea/common/img/support/firmware_update/Latest%20software%20version.pdf',
    'T-400S': 'https://global-sei.com/sumitomo-electric-splicers/emea/common/img/support/firmware_update/Latest%20software%20version.pdf',
    'T-72M12+': 'https://global-sei.com/sumitomo-electric-splicers/emea/common/img/support/firmware_update/Latest%20software%20version.pdf',
}
