# Theoretical Foundations: Windows Virtual Memory Management

## 1. Introduction
Modern operating systems face the fundamental challenge of managing scarce physical memory (RAM) among multiple concurrent processes while ensuring process isolation, performance, and security.

While classical textbook literature often illustrates paging using simple global replacement policies (e.g. Belady's MIN, global FIFO, or global LRU), modern commercial operating systems—most notably Microsoft Windows NT, 2000, XP, 7, 10, and 11—utilize a sophisticated **two-tier paging architecture**.

This document outlines the core theoretical principles modeled in the Windows Memory Manager Simulator.

---

## 2. Process Working Sets

In Windows, the physical frames assigned to an active process are collectively known as its **Working Set (WS)**. 

### 2.1 Working Set Quotas & Limits
- Every process possesses a Working Set Minimum ($WS_{\min}$) and Working Set Maximum ($WS_{\max}$).
- In this simulator, default limits are assigned as $[4, 4, 3]$ pages for processes $P_1, P_2, P_3$ respectively across the $16$ available physical frames.
- By capping the number of pages a single process can lock in physical memory, the operating system prevents a memory-intensive thread from starving other workloads.

### 2.2 Working Set Trimming
When a process references a new page and its working set already meets or exceeds its allotted quota, the kernel initiates **Working Set Trimming**:
1. The kernel scans the resident pages of the target process using an age-based heuristic (approximated here by timestamp $u$).
2. The oldest resident page is selected as the victim.
3. The victim is detached from the process's valid hardware page table (PTE Valid bit is cleared to 0).
4. Rather than discarding or overwriting the frame immediately, the kernel examines the hardware **Dirty Bit ($d$)**:
   - **Clean Page ($d=0$):** Placed onto the **Standby List**.
   - **Dirty Page ($d=1$):** Placed onto the **Modified List**.

---

## 3. The Page Frame Number (PFN) Database

The physical memory subsystem is organized around the **Page Frame Number (PFN) Database**. Each physical frame in RAM is represented by an entry in this array:

### 3.1 Frame Classification Lists
1. **Active / Valid:** Mapped in a process's working set (Valid bit = 1 in the processor's Page Table Entry).
2. **Standby List:** Contains clean pages that were trimmed from working sets. The physical frame retains its original virtual memory association and data.
3. **Modified List:** Contains pages that have been modified by write operations ($d=1$) and trimmed from working sets. Must be written to disk before reuse.
4. **Free List:** Unallocated physical frames that contain stale data and have not yet been zero-filled.
5. **Zeroed List:** Frames that have been filled with zeroes by the idle Zero-Page Thread, ready for demand-zero allocations.

---

## 4. Soft Faults vs. Hard Faults

A critical performance differentiator in Windows is the distinction between **Soft Page Faults** and **Hard Page Faults**:

$$\text{Total Faults} = \text{Soft Faults} + \text{Hard Faults}$$

### 4.1 Soft Page Faults (In-Memory Transition)
- Occurs when a process accesses a page that is not in its active working set, but the frame is still present in RAM on either the **Standby List** or the **Modified List**.
- **Action:** The kernel locates the frame in the PFN database, unlinks it from the list, sets its PTE Valid bit to 1, and re-inserts it into the process's working set.
- **Disk I/O Cost:** **Zero disk reads**. The CPU overhead is limited to a brief kernel exception handler execution, rendering it orders of magnitude faster than a disk read.

### 4.2 Hard Page Faults (Disk / Pagefile I/O)
- Occurs when the requested page does not exist anywhere in physical RAM.
- **Action:** 
  1. The kernel allocates a physical frame from the Zeroed list, Free list, or reclaims the oldest frame from the Standby list.
  2. The kernel initiates a synchronous disk read from the paging file (`pagefile.sys`) or mapped executable file.
- **Disk I/O Cost:** Full secondary storage latency (e.g. milliseconds for HDD or tens of microseconds for NVMe SSD).

---

## 5. Kernel Support Worker Threads

### 5.1 Modified Page Writer
- The Modified Page Writer is an asynchronous kernel worker thread.
- When the modified list grows large or the system enters memory pressure, it flushes dirty frames in contiguous blocks to `pagefile.sys`.
- Upon successful disk write, the dirty bit is cleared ($d=0$) and the frames are moved to the **Standby List**, making them eligible for reallocation while remaining recoverable via soft faults.

### 5.2 Zero-Page Thread
- Operates at priority 0 (the lowest thread priority in the Windows NT scheduler, running only when no other threads are ready to execute).
- Consumes free frames from the **Free List**, clears all bytes to zero, and inserts them onto the **Zeroed List**.
- **Security Justification:** Prevents information leakage between processes (ensuring a newly allocated page does not expose private memory previously used by another process).

---

## 6. Memory Thrashing

**Thrashing** is a pathological operating system condition where the system spends significantly more time performing paging I/O than executing user-level application logic:
- Occurs when the sum of the working sets of all active processes exceeds the total available physical memory:
  $$\sum_{i} WS_i > \text{Total Physical Frames}$$
- Each process continuously evicts pages required in subsequent clock cycles, creating a cascading sequence of hard page faults.
- In this simulator, thrashing is detected when available free/zeroed frames are exhausted and $\ge 50\%$ of the recent 20 memory accesses trigger hard faults.

---

## 7. Comparative Algorithms & Belady's Anomaly

The simulator includes an interactive algorithm lab comparing:
- **FIFO (First-In, First-Out):** Evicts the oldest page brought into memory. Prone to **Belady's Anomaly** (e.g. On the string `1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5`, increasing frames from 3 to 4 increases faults from 9 to 10).
- **LRU (Least Recently Used):** A stack algorithm immune to Belady's Anomaly; evicts the page not accessed for the longest time.
- **Clock (Second Chance):** An efficient hardware-approximated LRU using circular reference bits.
- **OPT (Belady's MIN):** The theoretical provable lower bound; evicts the page that will not be used for the longest period in the future.
