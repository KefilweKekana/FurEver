# SOP — Manufacturing: Remanufacturing Flow

**Module**: Manufacturing (MRP)
**Scope**: Remanufacturing path — producing refurbished units from core units + replacement parts
**Task Name**: Manufacturing - configure remanufacturing flow and BoMs
**Date**: 13 April 2026
**Author**: Mpho Kekana

---

## 1. Overview

The remanufacturing path is a **secondary workflow** triggered when a repair technician determines during diagnosis that a core unit needs to be refurbished rather than simply repaired. A Manufacturing Order (MO) consumes a core unit and replacement parts from stock, and produces a refurbished unit into stock.

**Flow**: Repair Diagnosis → Create MO from Repair (server action) → Produce → Auto-linked back to Repair

---

## 2. Prerequisites

| Item | Detail |
|------|--------|
| Manufacturing app | Installed and configured |
| Settings enabled | Shop Floor, Quality, Unlock Manufacturing Orders |
| Operation Type config | "Create New Lots/Serial Numbers for Components" and "Use Existing Lots/Serial Numbers for Components" enabled on Manufacturing operation type |
| Bill of Materials | Created for each refurbished product (e.g. REF-SAMPLE-BCM) |
| Component stock | Core units and replacement parts must be in stock with lot/serial numbers |
| Manufacture route | Enabled on the finished product (Product → Inventory tab → Routes → ☑ Manufacture) |

---

## 3. Bill of Materials (BoM) Structure

Each remanufacturable product needs a BoM:

| Field | Value |
|-------|-------|
| **Product** | The refurbished/finished product (e.g. REF-SAMPLE-BCM) |
| **BoM Type** | Manufacture this product |
| **Quantity** | 1 |
| **Components** | Core unit (e.g. CORE-SAMPLE-BCM, Qty 1) + Replacement parts (e.g. PART-SAMPLE-CAPACITOR, Qty 1) |

**To create a new BoM:**
1. Go to Manufacturing → Products → Bills of Materials
2. Click New
3. Set Product, BoM Type = "Manufacture this product", Quantity = 1
4. Add component lines with quantities
5. Save

---

## 4. Remanufacturing Process — Step by Step

### Step 1: Diagnosis Decision
- During repair diagnosis, the technician determines the unit needs remanufacturing
- Ensure the relevant **part** (component) is added to the repair's **Parts** tab

### Step 2: Verify Component Stock
- Before creating the MO, confirm components are in stock:
  - Go to Inventory → Products → search for the core unit and parts
  - Check "On Hand" quantities
- If stock is insufficient, receive parts first via Purchase or Inventory Adjustment

### Step 3: Create Manufacturing Order (from Repair)
**Preferred method — Server Action from repair form:**
1. On the repair order, click **⚙ Action → Create Manufacturing Order**
2. The server action reads the parts on the repair, finds the matching BoM, and creates the MO
3. The MO is auto-linked to the repair's **Manufacturing Order** field (Admin & Links tab)
4. You are redirected to the new MO in Draft status

**Safety checks built into the server action:**
- If no parts are on the repair → error message
- If no BoM matches the parts → error message
- If multiple BoMs match → error message (create MO manually instead)

**Alternative method — Manual creation:**
1. Go to Manufacturing → Operations → Manufacturing Orders
2. Click New
3. Set Product (the refurbished product), BoM auto-populates
4. Click Confirm
5. Manually link the MO on the repair's Admin & Links tab

### Step 4: Check Availability
1. Click **Check Availability**
2. All components should show **Available** (green badge)
3. If any show "Not Available" — resolve stock issue first

### Step 5: Assign Lot/Serial Numbers
1. For each component, click **Details** and assign or select a **Lot/Serial Number**
2. For the finished product, click **Generate Serial** or enter a serial manually
3. Set **Quantity** to the amount being produced

### Step 6: Produce
1. Click **Produce All**
2. MO moves to **Done** status
3. Stock moves are created automatically:
   - Components consumed FROM stock → Virtual Locations/Production
   - Finished product produced FROM Virtual Locations/Production → stock

### Step 7: Link MO to Repair Order
- If created via server action: **already auto-linked** — verify on Admin & Links tab
- If created manually: Open Admin & Links tab → search for the MO in the Manufacturing Order field → Save

---

## 5. Inventory Impact

| Product | Effect | Traceability |
|---------|--------|-------------|
| Core unit (e.g. CORE-SAMPLE-BCM) | Stock decreases by qty consumed | Tracked by Lot/Serial |
| Replacement parts (e.g. PART-SAMPLE-CAPACITOR) | Stock decreases by qty consumed | Tracked by Lot/Serial |
| Refurbished product (e.g. REF-SAMPLE-BCM) | Stock increases by qty produced | Tracked by Serial Number |

All moves are visible in Inventory → Reporting → Moves History, filtered by the MO reference.

---

## 6. Traceability Links

The repair order maintains links to all related records:

| Field | Location | Purpose |
|-------|----------|---------|
| CRM Lead | Admin & Links tab | Link to original enquiry |
| Sales Order | Admin & Links tab | Link to quotation/invoice |
| Manufacturing Order | Admin & Links tab | Link to remanufacturing MO |

---

## 7. Settings Reference

### Manufacturing Settings (Manufacturing → Configuration → Settings)
- ☑ Shop Floor
- ☑ Quality
- ☑ Unlock Manufacturing Orders
- ☐ Work Orders (not needed)
- ☐ Subcontracting (not needed)
- ☐ By-Products (not needed)

### Operation Type (Inventory → Configuration → Operations Types → Manufacturing)
- ☑ Create New Lots/Serial Numbers for Components
- ☑ Use Existing Lots/Serial Numbers for Components

### Product Setup (for each refurbished product)
- Inventory tab → Routes → ☑ Manufacture

---

## 8. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "You need to supply a Lot/Serial Number" | Components have lot tracking enabled | Click Details on each component line to assign lots, and Generate Serial for finished product |
| "Not allowed to create lots for components" | Operation type missing permission | Inventory → Configuration → Operations Types → Manufacturing → tick "Create New Lots/Serial Numbers for Components" |
| Component shows "Not Available" | Insufficient stock | Do inventory adjustment or receive stock first |
| BoM not auto-populating on MO | Manufacture route not enabled on product | Product → Inventory tab → Routes → tick Manufacture |
| "No parts added to this repair order" | Server action triggered with empty Parts tab | Add parts to the repair before running the action |
| "No manufacturing BoM found for the parts" | Parts on the repair don't match any BoM components | Check the BoM components match the parts on the repair |
| "Multiple BoMs match" | Same part appears in multiple BoMs | Create the MO manually from Manufacturing app |

---

## 9. Server Action Reference

**Name**: Create Manufacturing Order
**Model**: Repair Order (repair.order)
**Type**: Execute Code
**Binding**: Action menu on repair.order (⚙ Action dropdown)

**Logic:**
1. Reads parts from the repair's move lines
2. Searches `mrp.bom.line` for BoMs containing those parts (manufacture type only, not kits)
3. Validates: exactly one BoM must match
4. Creates MO for the BoM's finished product with quantity 1
5. Sets MO origin to the repair reference (e.g. "RO/AX029256")
6. Writes the MO link back to the repair's `x_studio_manufacturing_order` field

---

## 9. Configuration Summary

| # | What was configured | Where |
|---|-------------------|-------|
| 1 | Manufacturing settings verified | Manufacturing → Configuration → Settings |
| 2 | Lot creation enabled on operation type | Inventory → Configuration → Operations Types → Manufacturing |
| 3 | BoM created (REF-SAMPLE-BCM) | Manufacturing → Products → Bills of Materials |
| 4 | Manufacture route enabled on product | REF-SAMPLE-BCM → Inventory tab → Routes |
| 5 | Manufacturing Order link field added | Repair Order → Admin & Links tab (Studio) |
| 6 | MO tested end-to-end | WH/MO/00021 — Draft → Confirmed → To Close → Done |
| 7 | Inventory flow verified | Components consumed, finished product produced, lot traceability confirmed |

---

*SOP created by Mpho Kekana — Autolectronix Odoo 19 Implementation*
