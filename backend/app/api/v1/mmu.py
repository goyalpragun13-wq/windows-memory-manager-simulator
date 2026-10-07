"""
MMU and address translation API endpoints.
"""

from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_kernel
from app.core.vmm import WindowsMemoryManager
from app.core.types import AddressTranslationResult, PageTableEntry
from app.core.mmu import MMU
from app.schemas.simulation import TranslateAddressRequest

router = APIRouter(prefix="/mmu", tags=["MMU & Address Translation"])


@router.post("/translate", response_model=AddressTranslationResult)
def translate_virtual_address(
    req: TranslateAddressRequest,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """
    Translate a virtual byte address to a physical address via MMU simulation.
    Supports hexadecimal strings (e.g. '0x2A3C') or decimal integers.
    """
    raw_addr = req.virtual_address
    try:
        if isinstance(raw_addr, str):
            clean = raw_addr.strip()
            if clean.lower().startswith("0x"):
                addr = int(clean, 16)
            else:
                addr = int(clean)
        else:
            addr = int(raw_addr)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid virtual address format. Must be an integer or hex string like '0x2A3C'."
        )

    res = kernel.translate_and_access(
        virtual_address=addr,
        process_id=req.process_id,
        is_write=req.is_write
    )
    return res


@router.get("/page-table/{process_id}", response_model=List[PageTableEntry])
def get_process_page_table(
    process_id: int,
    kernel: WindowsMemoryManager = Depends(get_kernel)
):
    """
    Inspect the architectural Page Table for a process, showing Valid/Transition/Invalid
    flags, mapped physical frame numbers, dirty bits, and TLB status.
    """
    if not (0 <= process_id <= 2):
        raise HTTPException(status_code=400, detail="Process ID must be 0, 1, or 2.")

    return MMU.get_page_table_entries(
        process_id=process_id,
        frames=kernel.pfn_db.frames,
        tlb=kernel.tlb
    )


@router.get("/tlb")
def get_tlb_status(kernel: WindowsMemoryManager = Depends(get_kernel)):
    """Retrieve current TLB entries and hit/miss metrics."""
    return {
        "capacity": kernel.tlb.capacity,
        "raw_keys": kernel.tlb.entries,
        "entries": [
            {"process_id": k // 100, "page_number": k % 100}
            for k in kernel.tlb.entries
        ],
        "hits": kernel.tlb.hits,
        "misses": kernel.tlb.misses,
        "hit_rate_pct": kernel.stats.tlb_hit_rate_pct,
    }
