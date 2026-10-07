"""
Shared simulation singleton instance and dependencies.
"""

from app.core.vmm import WindowsMemoryManager

# Global kernel simulator instance
kernel_instance = WindowsMemoryManager()


def get_kernel() -> WindowsMemoryManager:
    """Dependency injector providing the shared kernel simulation instance."""
    return kernel_instance
