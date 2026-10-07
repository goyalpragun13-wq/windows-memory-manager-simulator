# REST API Reference & Specification

The Windows Virtual Memory Manager Simulator exposes a modular REST API built on FastAPI. Complete interactive documentation is accessible via Swagger UI at `/docs` or ReDoc at `/redoc`.

Base URL: `http://localhost:8000/api/v1`

---

## 1. System Health & State

### `GET /health`
Returns service availability status.
```json
{
  "status": "ok",
  "service": "Windows Memory Manager Simulator API"
}
```

### `GET /api/v1/sim/state`
Returns the complete memory manager kernel snapshot including all 16 frames, system lists, working sets, telemetry stats, and event log.

---

## 2. Memory Subsystem Operations

### `POST /api/v1/sim/access`
Simulates a memory reference.
- **Request Body:**
  ```json
  {
    "process_id": 0,
    "page_number": 2,
    "is_write": false
  }
  ```
- **Response:**
  ```json
  {
    "fault_type": "hit",
    "frame": { "i": 2, "s": "act", "p": 0, "pg": 2, "d": 0, "u": 14 },
    "state": { ... }
  }
  ```

### `POST /api/v1/sim/flush`
Triggers the Modified Page Writer to flush all dirty pages from the Modified list to disk, clearing dirty flags and moving frames to Standby.

### `POST /api/v1/sim/zero-step`
Executes one step of the idle-priority Zero-Page Thread, converting the oldest Free frame to Zeroed.

### `POST /api/v1/sim/kill/{process_id}`
Terminates a process, flushes its TLB entries, and returns all its allocated physical frames to the Free list.

### `POST /api/v1/sim/limit`
Sets the Working Set limit (quota) for a process. Automatically executes working set trimming if current residency exceeds the new quota.
- **Request Body:**
  ```json
  {
    "process_id": 0,
    "limit": 5
  }
  ```

### `POST /api/v1/sim/reset`
Resets the entire simulator back to initial boot conditions.

---

## 3. MMU & Address Translation

### `POST /api/v1/mmu/translate`
Decomposes a virtual address, queries the TLB, handles demand paging, and computes the 32-bit physical byte address.
- **Request Body:**
  ```json
  {
    "virtual_address": "0x2A3C",
    "process_id": 0,
    "is_write": false
  }
  ```
- **Response:**
  ```json
  {
    "virtual_address": 10812,
    "virtual_address_hex": "0x2A3C",
    "page_number": 2,
    "offset": 2620,
    "offset_hex": "0xA3C",
    "tlb_hit": true,
    "fault_type": "hit",
    "frame_number": 2,
    "physical_address": 31292,
    "physical_address_hex": "0x7A3C",
    "message": "VA 0x2A3C -> VPN 2, Offset 0xA3C. TLB HIT, HIT FAULT. Frame #2 => PA 0x7A3C."
  }
  ```

### `GET /api/v1/mmu/page-table/{process_id}`
Returns the architectural page table for the specified process.

---

## 4. Scenarios & Experiment Lab

### `GET /api/v1/scenarios`
Returns the list of 6 pre-configured educational scenarios.

### `POST /api/v1/scenarios/{id}/run`
Executes the scenario and returns pass/fail validation assertions against expected hardware counters.

### `POST /api/v1/algorithms/lab`
Runs replacement algorithms (FIFO, LRU, Clock, OPT) across frame sweeps with automated Belady's Anomaly detection.

### `POST /api/v1/telemetry/tests/run`
Executes the complete automated unit verification suite.
