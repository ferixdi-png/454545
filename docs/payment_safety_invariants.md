# PAYMENT SAFETY INVARIANTS

## Overview

This document defines strict financial invariants that **MUST NEVER** be violated, even in error scenarios.

## Core Invariants

### 1. Charge Only on Success

**Rule:** Money is charged **ONLY** when generation succeeds.

**Implementation:**
- `commit_charge()` called **ONLY** when `gen_result['success'] == True`
- All other paths call `release_charge()` (no charge)

**Guarantee:**
- ✅ Timeout → No charge
- ✅ KIE fail → No charge
- ✅ Network error → No charge
- ✅ Invalid input → No charge

### 2. Auto-Refund on Failure

**Rule:** On any failure, charge is automatically released.

**Implementation:**
- `release_charge()` called automatically on:
  - `gen_result['success'] == False`
  - `error_code == 'TIMEOUT'`
  - `error_code == 'KIE_API_ERROR'`
  - Any other error

**Guarantee:**
- ✅ No manual intervention required
- ✅ No stuck charges
- ✅ User always knows money status

### 3. Idempotency Protection

**Rule:** Repeated operations are safe (no-op).

**Implementation:**
- `commit_charge()` checks `_committed_charges` set
- `release_charge()` checks `_released_charges` set
- Repeated calls return `already_committed` / `already_released`

**Guarantee:**
- ✅ Double-click confirm → No double charge
- ✅ Network retry → No double charge
- ✅ Race conditions → No double charge

### 4. Clear Status Messages

**Rule:** User **ALWAYS** sees unambiguous payment status.

**Status Messages:**
- `pending` → "Ожидание оплаты"
- `committed` → "Оплачено"
- `released` → "Деньги не списаны"
- `already_committed` → "Оплата уже подтверждена"
- `already_released` → "Оплата уже отменена"

**Guarantee:**
- ✅ No ambiguous states
- ✅ No "unknown" status
- ✅ User always knows money status

## Unhappy Scenarios

### Scenario 1: Generation Timeout

**Flow:**
1. User starts generation
2. Pending charge created
3. Generation times out
4. `release_charge()` called automatically
5. User sees: "Деньги не списаны"

**Invariant Check:**
- ✅ Charge NOT committed
- ✅ Charge released
- ✅ User sees clear status
- ✅ No manual intervention

### Scenario 2: KIE API Fail

**Flow:**
1. User starts generation
2. Pending charge created
3. KIE API returns `fail` state
4. `release_charge()` called automatically
5. User sees: "Деньги не списаны"

**Invariant Check:**
- ✅ Charge NOT committed
- ✅ Charge released
- ✅ User sees clear status
- ✅ No manual intervention

### Scenario 3: Double Confirmation Click

**Flow:**
1. User clicks confirm payment
2. `commit_charge()` called → charge committed
3. User clicks confirm again (network retry, double-click, etc.)
4. `commit_charge()` called again → returns `already_committed`
5. User sees: "Оплата уже подтверждена"

**Invariant Check:**
- ✅ Charge committed only once
- ✅ Second call is no-op
- ✅ User sees clear status
- ✅ No double charge

### Scenario 4: Invalid OCR

**Flow:**
1. User sends payment screenshot
2. OCR processing fails (low confidence, wrong text)
3. OCR returns `success=False, needs_retry=True`
4. **NO charge created** (handler checks OCR before charge)
5. User sees: "Распознавание неуверенно. Пожалуйста, отправьте скриншот еще раз."

**Invariant Check:**
- ✅ No charge created
- ✅ User asked to retry
- ✅ No money involved
- ✅ Clear instructions

## Success Criteria

✅ **Financial invariants are unbreakable**

- Timeout → No charge
- Fail → No charge
- Double-click → No double charge
- Invalid OCR → No charge
- Network error → No charge
- User always sees clear status
- No stuck charges
- No manual intervention required (except payment API failures)

