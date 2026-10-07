"""
Configuration and architectural constants for the Windows Memory Manager Simulator.
"""

NUM_FRAMES = 16
PAGES_PER_PROCESS = 10
NUM_PROCESSES = 3
DEFAULT_WORKING_SET_LIMITS = [4, 4, 3]

PAGE_SIZE = 4096                  # 4 KB pages
PAGE_OFFSET_BITS = 12             # 2^12 = 4096
OFFSET_MASK = 0xFFF               # Low 12 bits

TLB_CAPACITY = 4                  # 4-entry associative TLB (LRU eviction)
MAX_LOG_ENTRIES = 50              # Keep last 50 kernel events in ring log
MAX_HISTORY_ENTRIES = 100         # Performance history trendline points

PROCESS_NAMES = ["Process P1", "Process P2", "Process P3"]
PROCESS_COLORS = ["#059669", "#7c3aed", "#ea580c"]  # Green, Purple, Orange

PFN_STATE_NAMES = {
    "free": "Free list",
    "zero": "Zeroed list",
    "stby": "Standby list",
    "mod": "Modified list",
    "act": "Active working set",
}

PFN_STATE_COLORS = {
    "free": "#94a3b8",   # Slate / gray
    "zero": "#0284c7",   # Sky blue
    "stby": "#eab308",   # Amber / yellow
    "mod": "#e11d48",    # Rose / red
    "act": "#10b981",    # Emerald
}
