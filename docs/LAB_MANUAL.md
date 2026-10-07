# University Operating Systems Laboratory Manual: Virtual Memory Subsystem

## Course: CS301 / Operating Systems & Architecture
**Project:** Windows NT/10/11 Virtual Memory Manager Architecture & Paging Simulator  

---

## Lab Objective
To explore the behavior of multi-process virtual address spaces, working set trimming, standby/modified page caching, soft vs. hard page faults, hardware MMU address translation, and page replacement algorithm bounds.

---

## Lab Exercise 1: Demand Paging & Hard Page Faults
1. Launch the simulator and ensure the system is in its initial boot state (`Reset System`).
2. Observe that all 16 physical frames reside on the **Free List**.
3. Under **Process P1**, click on virtual page numbers `0`, `1`, and `2` in read mode.
4. **Questions for Report:**
   - How many disk reads were logged in the telemetry panel?
   - What list did the allocated physical frames come from (Zeroed or Free)?
   - Explain why the first access to any virtual page in a newly loaded process invariably results in a hard page fault.

---

## Lab Exercise 2: Working Set Trimming & Soft Page Faults
1. For **Process P1** (working set limit = 4), access pages `3` and `4`.
2. Observe the state of the first page accessed (Page 0).
3. Access Page `0` once again.
4. **Questions for Report:**
   - Did the second access to Page `0` trigger a hard fault or a soft fault?
   - Compare the **Disk Reads** counter before and after touching Page `0`. Did the disk read count increment?
   - Explain the architectural purpose of the **Standby List** in Windows and how it improves desktop application switching performance.

---

## Lab Exercise 3: Dirty Pages & The Modified Page Writer
1. Toggle the mode button to **Write Mode** (marked with `*`).
2. Under Process P1, access pages `5`, `6`, `7`, `8`, and `9`.
3. Observe the contents of the **Modified List** (red chips).
4. Click **Run Modified Page Writer**.
5. **Questions for Report:**
   - Why can dirty pages not be moved directly to the Standby list upon being trimmed?
   - What happened to the dirty flags (`*`) after running the Modified Page Writer?
   - How does batching modified page writes into contiguous disk blocks improve secondary storage throughput?

---

## Lab Exercise 4: Address Translation & TLB Simulation
1. In the MMU section, enter the virtual address `0x2A3C` and click **Translate & Access**.
2. **Questions for Report:**
   - What is the Virtual Page Number (VPN) and byte offset in decimal and hexadecimal?
   - Did the translation result in a TLB Hit or TLB Miss?
   - Using the mapped Physical Frame Number (PFN), show the manual calculation for the 32-bit Physical Address (PA).
   - How does the 4-entry associative TLB LRU eviction policy behave when a 5th distinct virtual page is accessed?

---

## Lab Exercise 5: Replacement Algorithms & Belady's Anomaly
1. Navigate to the **Experiment Lab** section.
2. Select the **Belady String** workload: `1 2 3 4 1 2 5 1 2 3 4 5`.
3. Click **Run Lab Experiment**.
4. **Questions for Report:**
   - Compare the fault count for FIFO at 3 physical frames versus 4 physical frames. Does increasing frame allocation reduce page faults?
   - Does LRU or Clock exhibit Belady's Anomaly on this reference string? Why or why not?
   - Verify that the Optimal (OPT) algorithm achieves the theoretical minimal fault count across all frame sizes ($1 \dots 10$).

---

## Grading Rubric (100 Points Total)

| Section | Description | Weight |
|---|---|---|
| **Part I** | Completion of Lab Exercises 1 through 5 with recorded telemetry | 35 pts |
| **Part II** | Theoretical Analysis of Soft Faults & PFN state machine | 25 pts |
| **Part III** | Automated Verification Test Suite pass rate (100% on self-test runner) | 20 pts |
| **Part IV** | Code quality, commit history, and technical architecture review | 20 pts |
